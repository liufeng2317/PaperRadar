# Author: Feng Liu
# Affiliation: Shanghai Jiao Tong University
# Contact: Liufeng2317@sjtu.edu.cn
# Citation requested: If you use this codebase or derivative workflows,
# please cite/acknowledge the original author in publications and releases.

import json
import os
import time
from glob import glob
from pathlib import Path

import cv2
import fire
import httpx
import json_repair
import numpy as np
from dotenv import load_dotenv
from loguru import logger
from tqdm import tqdm

logger.add(
    sink="./logs/mineru_logs/llm_aid.log",
    encoding="utf-8",
)
from mineru.backend.pipeline.pipeline_middle_json_mkcontent import merge_para_with_text
from mineru.backend.utils import cross_page_table_merge  # Requires MinerU 2.6.4+.
from mineru.backend.vlm.vlm_magic_model import MagicModel
from mineru.utils.config_reader import get_table_enable
from mineru.utils.cut_image import cut_image_and_table
from mineru.utils.enum_class import ContentType
from mineru.utils.hash_utils import bytes_md5
from mineru.utils.pdf_image_tools import get_crop_img
from mineru.version import __version__

from mineru.backend.vlm.vlm_middle_json_mkcontent import union_make as vlm_union_make
from mineru.cli.common import convert_pdf_bytes_to_bytes_by_pypdfium2, read_fn
from mineru.data.data_reader_writer import FileBasedDataWriter
from mineru.utils.enum_class import ImageType, MakeMode
from mineru.utils.pdf_image_tools import load_images_from_pdf
from mineru.backend.pipeline.pipeline_middle_json_mkcontent import union_make as pipeline_union_make
from openai import OpenAI

_MODULE_ROOT = Path(__file__).resolve().parent
# Prefer project/.env, then module-local fallback.
load_dotenv(dotenv_path=_MODULE_ROOT.parent / ".env")
load_dotenv(dotenv_path=_MODULE_ROOT.parent.parent / ".env")
load_dotenv(dotenv_path=_MODULE_ROOT / ".env")
from mineru.backend.pipeline.model_init import AtomModelSingleton

TITLE_AIDED_CONFIG = dict(
    model=os.getenv("PJLAB_API_CHAT_MODEL"),
    api_key=os.getenv("PJLAB_API_KEY"),
    base_url=os.getenv("PJLAB_API_BASE_URL"),
)
HEADING_LEVEL_IMPORT_SUCCESS = False


def llm_aided_title(page_info_list, title_aided_config, max_retries=3, think_mode=False):
    """Optimize the hierarchical structure of titles in a document using an LLM.

    Parameters
    ----------
    page_info_list : list
        List of page information dictionaries containing title blocks.
    title_aided_config : dict
        Configuration for the LLM, including model and API details.
    max_retries : int, optional
        Maximum number of retries for the LLM API call, by default 3.

    Returns:
    -------
    None
        Modifies the `page_info_list` in place by adding hierarchical levels to titles.
    """
    client = OpenAI(
        api_key=title_aided_config["api_key"],
        base_url=title_aided_config["base_url"],
        http_client=httpx.Client(verify=False),
    )
    title_dict = {}
    origin_title_list = []
    i = 0
    for page_info in page_info_list:
        blocks = page_info["para_blocks"]
        for block in blocks:
            if block["type"] == "title":
                origin_title_list.append(block)
                title_text = merge_para_with_text(block)

                if "line_avg_height" in block:
                    line_avg_height = block["line_avg_height"]
                else:
                    title_block_line_height_list = []
                    for line in block["lines"]:
                        bbox = line["bbox"]
                        title_block_line_height_list.append(int(bbox[3] - bbox[1]))
                    if len(title_block_line_height_list) > 0:
                        line_avg_height = sum(title_block_line_height_list) / len(title_block_line_height_list)
                    else:
                        line_avg_height = int(block["bbox"][3] - block["bbox"][1])

                title_dict[f"{i}"] = [title_text, line_avg_height, int(page_info["page_idx"]) + 1]
                i += 1
    title_optimize_prompt = f"""The input is a dictionary of all detected titles in one document.
Please assign a reasonable heading level to each title so the result follows a normal document hierarchy.

1. Each dictionary value is a list containing:
    - title text
    - average line height of the title block
    - page number

2. Preserve the input:
    - every input item is valid and must remain present
    - the output dictionary must contain exactly the same number of items as the input

3. Keep the original key-to-title mapping unchanged.

4. Optimize the hierarchy:
    - assign each title a suitable level based on semantic meaning
    - larger line height usually indicates a higher-level heading
    - heading levels should progress continuously without skipped levels
    - use at most four heading levels
    - output only the integer heading level for each title

5. Sanity-check the result:
    - review whether the level assignments are structurally reasonable
    - adjust inconsistent levels based on context and logical order
    - make sure the final hierarchy matches the document structure

IMPORTANT:
Return only the optimized heading-level dictionary in this format: {{title_id: heading_level}}.
{{
  0:1,
  1:2,
  2:2,
  3:3
}}
Do not return formatting, explanation, markdown, or any extra text.

Input title list:
{title_dict}

Corrected title list:
"""

    retry_count = 0
    dict_completion = None

    # Build API call parameters
    api_params = {
        "model": title_aided_config["model"],
        "messages": [
            {"role": "user", "content": title_optimize_prompt if think_mode else title_optimize_prompt + "/no_think"}
        ],
        "temperature": 0.7,
        "stream": False,
    }

    # Only add extra_body when explicitly specified in config
    if "enable_thinking" in title_aided_config:
        api_params["extra_body"] = {"enable_thinking": title_aided_config["enable_thinking"]}

    while retry_count < max_retries:
        try:
            completion = client.chat.completions.create(**api_params)
            content = completion.choices[0].message.content.strip()

            if "</think>" in content:
                idx = content.index("</think>") + len("</think>")
                content = content[idx:].strip()

            dict_completion = json_repair.loads(content)
            dict_completion = {int(k): int(v) for k, v in dict_completion.items()}

            if len(dict_completion) == len(title_dict):
                for i, origin_title_block in enumerate(origin_title_list):
                    origin_title_block["level"] = int(dict_completion[i])
                break
            else:
                logger.warning(
                    "The number of titles in the optimized result is not equal to the number of titles in the input."
                )
                retry_count += 1
        except Exception as e:
            logger.exception(e)
            retry_count += 1

    if dict_completion is None:
        logger.error("Failed to decode dict after maximum retries.")


def blocks_to_page_info(page_blocks, image_dict, page, image_writer, page_index) -> dict:
    """Convert blocks into page info."""
    scale = image_dict["scale"]
    page_pil_img = image_dict["img_pil"]
    page_img_md5 = bytes_md5(page_pil_img.tobytes())
    width, height = map(int, page.get_size())

    magic_model = MagicModel(page_blocks, width, height)
    image_blocks = magic_model.get_image_blocks()
    table_blocks = magic_model.get_table_blocks()
    title_blocks = magic_model.get_title_blocks()
    discarded_blocks = magic_model.get_discarded_blocks()
    code_blocks = magic_model.get_code_blocks()
    ref_text_blocks = magic_model.get_ref_text_blocks()
    phonetic_blocks = magic_model.get_phonetic_blocks()
    list_blocks = magic_model.get_list_blocks()

    # Optionally run OCR detection on cropped title blocks for heading refinement.
    if HEADING_LEVEL_IMPORT_SUCCESS:
        atom_model_manager = AtomModelSingleton()
        ocr_model = atom_model_manager.get_atom_model(
            atom_model_name="ocr", ocr_show_log=False, det_db_box_thresh=0.3, lang="ch_lite"
        )
        for title_block in title_blocks:
            title_pil_img = get_crop_img(title_block["bbox"], page_pil_img, scale)
            title_np_img = np.array(title_pil_img)
            # Add white padding around the cropped title image before OCR.
            title_np_img = cv2.copyMakeBorder(title_np_img, 50, 50, 50, 50, cv2.BORDER_CONSTANT, value=[255, 255, 255])
            title_img = cv2.cvtColor(title_np_img, cv2.COLOR_RGB2BGR)
            ocr_det_res = ocr_model.ocr(title_img, rec=False)[0]
            if len(ocr_det_res) > 0:
                # Use the average detected text-box height as an additional title signal.
                avg_height = np.mean([box[2][1] - box[0][1] for box in ocr_det_res])
                title_block["line_avg_height"] = round(avg_height / scale)

    text_blocks = magic_model.get_text_blocks()
    interline_equation_blocks = magic_model.get_interline_equation_blocks()

    all_spans = magic_model.get_all_spans()
    # Crop visual spans that should be emitted as external image assets.
    for span in all_spans:
        if span["type"] in [ContentType.IMAGE, ContentType.TABLE, ContentType.INTERLINE_EQUATION]:
            span = cut_image_and_table(span, page_pil_img, page_img_md5, page_index, image_writer, scale=scale)

    page_blocks = []
    page_blocks.extend(
        [
            *image_blocks,
            *table_blocks,
            *code_blocks,
            *ref_text_blocks,
            *phonetic_blocks,
            *title_blocks,
            *text_blocks,
            *interline_equation_blocks,
            *list_blocks,
        ]
    )
    # Restore reading order after merging block groups.
    page_blocks.sort(key=lambda x: x["index"])

    page_info = {
        "para_blocks": page_blocks,
        "discarded_blocks": discarded_blocks,
        "page_size": [width, height],
        "page_idx": page_index,
    }
    return page_info


def result_to_middle_json(
    model_output_blocks_list, images_list, pdf_doc, image_writer, llm_aid=True, llm_aided_config=None
):
    """Convert model output blocks and images into a structured JSON format.

    Parameters
    ----------
    model_output_blocks_list : list
        List of blocks output by the model for each page.
    images_list : list
        List of image dictionaries containing page image data.
    pdf_doc : object
        PDF document object representing the input PDF.
    image_writer : object
        Writer object for saving processed images.
    llm_aided_config : dict, optional
        Configuration dictionary for LLM-aided title optimization.

    Returns: dict of middle result
    -------
    dict
        A JSON object containing structured information about the PDF.
    """
    middle_json = {"pdf_info": [], "_backend": "vlm", "_version_name": __version__}
    for index, page_blocks in enumerate(model_output_blocks_list):
        page = pdf_doc[index]
        image_dict = images_list[index]
        page_info = blocks_to_page_info(page_blocks, image_dict, page, image_writer, index)
        middle_json["pdf_info"].append(page_info)

    # Merge tables that continue across page boundaries.
    table_enable = get_table_enable(os.getenv("MINERU_VLM_TABLE_ENABLE", "True").lower() == "true")
    if table_enable:
        cross_page_table_merge(middle_json["pdf_info"])

    # Refine heading levels with the configured LLM when enabled.
    if llm_aid:
        llm_aided_title_start_time = time.time()
        title_aided_config = TITLE_AIDED_CONFIG if llm_aided_config is None else llm_aided_config
        try:
            llm_aided_title(middle_json["pdf_info"], title_aided_config)
        except Exception as e:
            logger.warning(f"Warning: llm optimize title failed: {e}")
        logger.info(f"llm aided title time: {round(time.time() - llm_aided_title_start_time, 2)}")

    # Close the PDF document after all page images and blocks have been consumed.
    pdf_doc.close()
    return middle_json


def llm_aid_mineru_result(extract_path, origin_pdf_path):
    mineru_pdf_name = os.path.basename(glob(os.path.join(extract_path, "*_origin.pdf"))[0]).split("_origin")[0]
    if os.path.isfile(os.path.join(extract_path, f"{mineru_pdf_name}.md")):
        print(os.path.join(extract_path, f"{mineru_pdf_name}.md"), " exists!")
        return
    image_list, pdf_doc = load_images_from_pdf(
        convert_pdf_bytes_to_bytes_by_pypdfium2(read_fn(os.path.join(origin_pdf_path))),
        image_type=ImageType.PIL,
    )
    image_dir = os.path.join(extract_path, "images")
    md_writer, image_writer = FileBasedDataWriter(extract_path), FileBasedDataWriter(image_dir)
    with open(glob(os.path.join(extract_path, "*_model.json"))[0]) as fr:
        model_json = json.load(fr)

    try:
        middle_json = result_to_middle_json(
            model_json,
            image_list,
            pdf_doc,
            image_writer,
            llm_aid=True,
            llm_aided_config=dict(
                model=os.getenv("OPENAI_API_CHAT_MODEL"),
                api_key=os.getenv("OPENAI_API_KEY"),
                base_url=os.getenv("OPENAI_API_BASE_URL"),
            ),
        )
    except Exception as e:
        logger.warning(f"{extract_path} failed: {e}")
        return

    make_func = vlm_union_make
    markdown_content = make_func(middle_json["pdf_info"], MakeMode.MM_MD, image_dir)
    markdown_content = markdown_content.replace(image_dir, "images")
    md_writer.write_string(f"{mineru_pdf_name}.md", markdown_content)

def main(start_idx, end_idx):
    mineru_session_root = "/data/datasets/earth_corpus/mineru_outputs"
    sessions = sorted(os.listdir(mineru_session_root))[start_idx: end_idx]

    logger.info(f"{len(sessions)} sessions found!")
    for i, session in enumerate(tqdm(sessions)):
        session_path = os.path.join(mineru_session_root, session)
        try:
            origin_pdf_candidates = glob(os.path.join(session_path, "*_origin.pdf"))
            if not origin_pdf_candidates:
                logger.warning(f"[{i}/{len(sessions)}] {session}: no *_origin.pdf found, skip")
                continue
            origin_pdf_path = origin_pdf_candidates[0]
            logger.info(f"[{i}/{len(sessions)}] start {session}, pdf={origin_pdf_path}")
            llm_aid_mineru_result(session_path, origin_pdf_path)
            logger.info(f"[{i}/{len(sessions)}] {session} processed")
        except Exception as e:
            logger.exception(f"[{i}/{len(sessions)}] {session} failed: {e}")

if __name__ == "__main__":
    fire.Fire(main)
