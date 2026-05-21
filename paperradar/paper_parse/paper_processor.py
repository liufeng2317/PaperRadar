# Author: Feng Liu
# Affiliation: Shanghai Jiao Tong University
# Contact: Liufeng2317@sjtu.edu.cn
# Citation requested: If you use this codebase or derivative workflows,
# please cite/acknowledge the original author in publications and releases.

"""
This file is adapted from the original implementation by Jiong Wang (PJLAB).
"""

"""Processor for paper preparation. Functions to cover.

1. download paper via doi
2. extract PDF metadata
3. search reference list via doi or etc.
4. submit paper to mineru server for processing
5. download mineru parsed results
6. write result pdf information down to jsonl
"""

import argparse  # noqa: I001
import json
import os
import shutil
import time
from copy import deepcopy
from datetime import datetime
from glob import glob
from pathlib import Path
import requests
from dotenv import load_dotenv
from mineru.backend.pipeline.pipeline_middle_json_mkcontent import (
    union_make as pipeline_union_make,
)
from mineru.backend.vlm.vlm_middle_json_mkcontent import union_make as vlm_union_make
from mineru.cli.common import convert_pdf_bytes_to_bytes_by_pypdfium2, read_fn
from mineru.data.data_reader_writer import FileBasedDataWriter
from mineru.utils.enum_class import ImageType, MakeMode
from mineru.utils.pdf_image_tools import load_images_from_pdf
from loguru import logger
from tqdm import tqdm
from .llm_aid_utils import result_to_middle_json
from .utils import extract_title_from_metadata, extract_zip_to_named_folder


_MODULE_ROOT = Path(__file__).resolve().parent
# Prefer project/.env, then module-local fallback.
load_dotenv(dotenv_path=_MODULE_ROOT.parent / ".env")
load_dotenv(dotenv_path=_MODULE_ROOT.parent.parent / ".env")
load_dotenv(dotenv_path=_MODULE_ROOT / ".env")

MAX_DOWNLOAD_PERIOD = 300
MINERU_BATCH_SIZE_LIMIT = 200
LOG_DIR = "./logs/pdf_process"


class TqdmLoggingWrapper:
    """Custom tqdm wrapper that logs progress to logger."""

    def __init__(self, tqdm_instance, logger_instance=None):
        self.tqdm = tqdm_instance
        self.logger = logger_instance or logger
        self.last_log = 0
        self.log_interval = 10  # Log every 10% or every 10 items

    def __iter__(self):
        for item in self.tqdm:
            # Log progress at intervals
            if self.tqdm.n % self.log_interval == 0 or self.tqdm.n == self.tqdm.total:
                percentage = (self.tqdm.n / self.tqdm.total * 100) if self.tqdm.total > 0 else 0
                rate = self.tqdm.format_dict.get("rate") or 0
                desc = self.tqdm.desc or ""
                self.logger.info(
                    f"Progress: {self.tqdm.n}/{self.tqdm.total} ({percentage:.1f}%) {desc} - {rate:.2f}it/s"
                )
            yield item

    def update(self, n=1):
        self.tqdm.update(n)
        # Log progress at intervals
        if self.tqdm.n % self.log_interval == 0 or self.tqdm.n == self.tqdm.total:
            percentage = (self.tqdm.n / self.tqdm.total * 100) if self.tqdm.total > 0 else 0
            rate = self.tqdm.format_dict.get("rate") or 0
            desc = self.tqdm.desc or ""
            self.logger.info(f"Progress: {self.tqdm.n}/{self.tqdm.total} ({percentage:.1f}%) {desc} - {rate:.2f}it/s")

    def close(self):
        self.tqdm.close()
        percentage = (self.tqdm.n / self.tqdm.total * 100) if self.tqdm.total > 0 else 0
        desc = self.tqdm.desc or ""
        self.logger.info(f"Completed: {self.tqdm.n}/{self.tqdm.total} ({percentage:.1f}%) {desc}")

    def __getattr__(self, attr):
        """Delegate all other attributes to the tqdm instance."""
        return getattr(self.tqdm, attr)


class PaperProcessor:
    """Processor for managing academic papers.

    This class provides methods for downloading papers, extracting metadata,
    uploading files to a server, and processing results from MinerU.
    """

    def __init__(
        self,
        pdf_dir,
        mineru_dir,
        doi_list=None,
        log_dir=LOG_DIR,
        num_workers=8,
        mineru_api_url=None,
        mineru_api_key=None,
        mineru_is_pipeline=False,
        llm_aid=True,
        max_download_period=MAX_DOWNLOAD_PERIOD,
    ):
        """Initialize the PaperProcessor with directories, API configurations, and other settings.

        Args:
            pdf_dir (str): Directory to store downloaded PDFs.
            mineru_dir (str): Directory to store MinerU results.
            doi_list (list or str): List of DOIs or path to a file containing DOIs.
            log_dir (str): Directory for logging.
            num_workers (int): Number of workers for parallel processing.
            mineru_api_url (str): Base URL for MinerU API.
            mineru_api_key (str): API key for MinerU.
            mineru_is_pipeline (bool): Whether to use the pipeline mode for MinerU.
        """
        if doi_list is None:
            self.doi_list = []
        elif isinstance(doi_list, list):
            self.doi_list = doi_list
        elif isinstance(doi_list, str) and os.path.isfile(doi_list):
            self.doi_list = self.load_doi_list(doi_list)
        else:
            self.doi_list = []

        # Read runtime env here (after dotenv has been loaded by caller module).
        self.mineru_api_url = mineru_api_url or os.getenv("MINERU_API_BASE", "")
        self.mineru_api_key = mineru_api_key or os.getenv("MINERU_API_KEY", "")
        self.mineru_is_pipeline = mineru_is_pipeline

        self.pdf_dir = pdf_dir
        self.mineru_dir = mineru_dir
        self.log_dir = log_dir
        self.num_workers = num_workers
        self.max_download_period = max_download_period

        self.mineru_header = {"Content-Type": "application/json", "Authorization": f"Bearer {self.mineru_api_key}"}

        # Initialize paper_downloader if available (optional for local processing)
        try:
            from paper_downloader import PaperDownloader
            self.paper_downloader = PaperDownloader(download_dir=self.pdf_dir)
        except (ImportError, ModuleNotFoundError):
            self.paper_downloader = None
            logger.debug("PaperDownloader not available - download functionality disabled")

        self.llm_aid = llm_aid
        self.llm_client_config = dict(
            api_key=os.getenv("PJLAB_API_KEY"),
            base_url=os.getenv("PJLAB_API_BASE_URL"),
            model=os.getenv("PJLAB_API_CHAT_MODEL"),
        )

    def load_doi_list(self, doi_list_path):
        """Load a list of DOIs from a file.

        Args:
            doi_list_path (str): Path to the file containing DOIs.

        Returns:
            list: A list of DOIs loaded from the file.
        """
        doi_list = list()
        with open(doi_list_path) as fr:
            doi_lines = fr.readlines()
            for doi_line in doi_lines:
                doi_list.append(doi_line.strip())
        return doi_list

    def download_pdf(self, doi_list):
        """Download PDF files based on a list of DOIs.

        Args:
            doi_list (list): A list of DOIs to download.

        Returns:
            list: A list of successfully downloaded DOIs.
        """
        result_list = list()
        if len(doi_list) == 1:
            cleaned_doi = self.paper_downloader.clean_doi(doi_list[0])
            filename = self.paper_downloader.clean_filename(cleaned_doi)
            success, filepath = self.paper_downloader.download_paper(doi_list[0], filename)
            if success:
                result_list.append(doi_list[0])
            else:
                logger.info(f"✗ Failed to download: {doi_list[0]}")
        else:
            results = self.paper_downloader.download_multiple_papers(doi_list, max_workers=self.workers)
            for doi, (success, filepath) in zip(doi_list, results):
                if success:
                    result_list.append(doi)
                else:
                    logger.info(f"✗ Failed to download: {doi}")
        return result_list

    def upload_file_to_url(self, file_path, upload_url):
        """Upload a file to a specified URL using an HTTP PUT request.

        Args:
            file_path (str): The path to the file to be uploaded.
            upload_url (str): The URL to which the file will be uploaded.

        Returns:
            bool: True if the upload is successful, False otherwise.
        """
        with open(file_path, "rb") as f:
            res_upload = requests.put(upload_url, data=f)
            if res_upload.status_code == 200:
                logger.info(f"{upload_url} upload success")
                return True
            else:
                logger.info(f"{upload_url} upload failed")
                return False

    def load_pdf_metadata(self, pdf_path):
        """Load metadata from PDF files in a specified directory.

        Args:
            pdf_path (str): Path to the directory containing PDF files.

        Returns:
            dict: A dictionary where keys are PDF filenames (without extension) and values are their metadata.
        """
        pdf_metadata = dict()
        pdf_list = sorted(glob(os.path.join(pdf_path, "*.pdf")))
        for pdf_path in pdf_list:
            pdf_name = os.path.basename(pdf_path).replace(".pdf", "")
            try:
                title, metadata = extract_title_from_metadata(pdf_path)
            except Exception:
                pass
                # title, metadata = extract_title_from_content(pdf_path)
            pdf_metadata[pdf_name] = dict()
            pdf_metadata[pdf_name]["title"] = title
            pdf_metadata[pdf_name]["metadata"] = metadata

    def pdf_to_mineru(self, file_path, upload_url):
        """Upload pdf file to MinerU URL."""
        with open(file_path, "rb") as f:
            res_upload = requests.put(upload_url, data=f)
            if res_upload.status_code == 200:
                logger.info(f"{upload_url} upload success")
            else:
                logger.info(f"{upload_url} upload failed")

    def upload_mineru_batch_task(
        self, pdf_dir=None, model_version="vlm", language="en", is_ocr=True, mineru_batch_size=MINERU_BATCH_SIZE_LIMIT
    ):
        """Upload multiple PDF files to MinerU server as batch task.

        Args:
            pdf_dir (str): path of PDF directory
            model_version (str, optional): model version of MinerU, vlm or pipeline. Defaults to "vlm".

        Returns:
            _type_: _description_
        """
        pdf_dir = pdf_dir or self.pdf_dir
        mineru_url = f"{self.mineru_api_url}/api/v4/file-urls/batch"

        file_dict_base = {"name": "", "data_id": "", "is_ocr": is_ocr, "language": language}

        file_path_list = sorted(glob(os.path.join(pdf_dir, "*.pdf")))

        file_list = list()
        for file_path in file_path_list:
            file_item_dict = deepcopy(file_dict_base)
            file_item_dict["name"] = os.path.basename(file_path)
            file_list.append(file_item_dict)

        num_batches = len(file_list) // mineru_batch_size + 1

        batch_task_dict = dict()
        for idx in range(num_batches):
            batch_file_list, batch_file_path_list = (
                file_list[idx * mineru_batch_size : (idx + 1) * mineru_batch_size],
                file_path_list[idx * mineru_batch_size : (idx + 1) * mineru_batch_size],
            )
            # batch_task_dict = dict()
            try:
                response = requests.post(
                    mineru_url,
                    headers=self.mineru_header,
                    json={
                        "files": batch_file_list,
                        "model_version": model_version,
                    },
                )

                if response.status_code == 200:
                    result = response.json()
                    logger.info("response success. trace_id:{}".format(result["trace_id"]))
                    if result["code"] == 0:
                        batch_id = result["data"]["batch_id"]
                        batch_task_dict[batch_id] = dict()
                        urls = result["data"]["file_urls"]

                        logger.info(f"batch_id:{batch_id}, {len(urls)} urls")
                        assert len(urls) == len(batch_file_path_list)

                        for i in TqdmLoggingWrapper(tqdm(range(0, len(urls)), ncols=80, desc="Uploading files")):
                            self.upload_file_to_url(batch_file_path_list[i], urls[i])
                            batch_task_dict[batch_id][os.path.basename(batch_file_path_list[i])] = {
                                "mineru_url": urls[i]
                            }
                            batch_task_dict[batch_id][os.path.basename(batch_file_path_list[i])]["file_path"] = (
                                os.path.abspath(batch_file_path_list[i])
                            )
                    else:
                        logger.info(f"apply upload url failed, reason:{result.msg}")
                else:
                    logger.info(f"response not success. status:{response.status_code} ,result:{response}")
            except Exception as err:
                logger.info(err)

        return batch_task_dict

    def get_mineru_task_status(self, batch_id, mineru_task_dict):
        """Retrieve and process the results of a MinerU batch task.

        Polls the MinerU API periodically until all files are done/failed or timeout occurs.

        Args:
            batch_id (str): The unique identifier for the batch task.
            mineru_task_dict (dict): A dictionary containing information about the batch task.

        Returns:
            dict: Updated dictionary with the results of the MinerU batch task.
        """
        url = f"{self.mineru_api_url}/api/v4/extract-results/batch/{batch_id}"
        num_files = len(list(mineru_task_dict.keys()))
        done_items = 0
        remain_file_idxes = list(range(num_files))  # 存储待处理的「文件索引」（如0、1、2...）
        tbar = TqdmLoggingWrapper(tqdm(total=num_files, desc=f"{batch_id}", ncols=160))
        start_time = time.time()

        # Poll until all files are done/failed or timeout
        # 循环条件：未完成数<总文件数 + 未超时 + 仍有待处理文件（避免死循环）
        while (
            done_items < num_files and (time.time() - start_time) < self.max_download_period and len(remain_file_idxes) > 0
        ):
            # ✓ FIX: Fetch fresh status from API on each polling iteration
            try:
                res = requests.get(url, headers=self.mineru_header, timeout=10)
            except requests.RequestException as e:
                logger.warning(f"API request failed: {e}, retrying in 5 seconds...")
                time.sleep(5)
                continue

            if res.status_code != 200:
                logger.warning(f"API returned status {res.status_code}, retrying in 5 seconds...")
                time.sleep(5)
                continue

            try:
                response_json = res.json()
            except ValueError as e:
                logger.warning(f"Failed to parse JSON response: {e}, retrying in 5 seconds...")
                time.sleep(5)
                continue

            if response_json.get("code") != 0:
                logger.warning(f"API returned error code: {response_json.get('msg')}, retrying in 5 seconds...")
                time.sleep(5)
                continue

            response_data = response_json.get("data")
            if not response_data:
                logger.warning("API returned no data, retrying in 5 seconds...")
                time.sleep(5)
                continue

            # Validate response matches expected file count
            if len(response_data.get("extract_result", [])) != num_files:
                logger.warning(
                    f"API returned {len(response_data.get('extract_result', []))} files, expected {num_files}, retrying..."
                )
                time.sleep(5)
                continue

            # 浅拷贝待处理文件索引（避免遍历中修改列表导致错乱）
            traverse_file_idxes = remain_file_idxes.copy()
            files_still_processing = False

            for file_idx in traverse_file_idxes:  # file_idx：原始文件列表的索引（如0代表第一个文件）
                # 获取当前文件的状态数据
                file_data = response_data["extract_result"][file_idx]
                file_name = file_data["file_name"]
                file_state = file_data.get("state", "")

                # 情况1：文件状态为「已完成」→ 记录下载URL
                # 任务状态: done=完成, waiting-file=等待上传, pending=排队中, running=解析中, failed=失败, converting=转换中
                if file_state == "done":
                    mineru_task_dict[file_name]["mineru_result_url"] = file_data.get("full_zip_url", "")
                    done_items += 1
                    remain_file_idxes.remove(file_idx)  # 按「值」删除待处理的文件索引
                    tbar.update(1)
                    logger.info(f"{file_name} ✓ Processing complete")

                # 情况2：文件有错误信息→视为处理完成（跳过）
                elif file_state == "failed":
                    err_msg = file_data.get("err_msg", "Unknown error")
                    logger.error(f"{file_name} ✗ Failed: {err_msg}")
                    done_items += 1
                    remain_file_idxes.remove(file_idx)  # 按「值」删除
                    tbar.update(1)

                # 情况3：文件仍在处理中 → 继续等待
                # 状态包括: waiting-file, pending, running, converting
                else:
                    files_still_processing = True
                    if file_state not in ["waiting-file", "pending", "running", "converting"]:
                        logger.debug(f"{file_name} - Unknown state: {file_state}")

            # ✓ FIX: If files are still processing, wait before next poll
            # If all files are done/failed, loop will exit naturally
            if files_still_processing and done_items < num_files:
                time.sleep(5)  # Poll every 5 seconds

        # 循环结束后，处理剩余未完成的文件（超时或一直未done）
        # Get final status for timeout message
        try:
            res = requests.get(url, headers=self.mineru_header, timeout=10)
            if res.status_code == 200:
                response_json = res.json()
                if response_json.get("code") == 0:
                    response_data = response_json.get("data", {})
                    for file_idx in remain_file_idxes:
                        file_name = response_data.get("extract_result", [{}])[file_idx].get("file_name", f"file_{file_idx}")
                        file_state = response_data.get("extract_result", [{}])[file_idx].get("state", "unknown")
                        logger.warning(f"{file_name} - Timed out after {self.max_download_period}s (final state: {file_state})")
        except Exception as e:
            logger.warning(f"Could not fetch final status for timeout files: {e}")
            for file_idx in remain_file_idxes:
                logger.warning(f"file_{file_idx} - Timed out after {self.max_download_period}s")

        tbar.close()
        return mineru_task_dict

    def download_mineru_results(self, batch_task_dict, num_tries=3, timeout=15):
        """Download MinerU parsed results via wget.

        Args:
            mineru_url_list (list): list of MinerU links
            num_tries (int, optional): number of trials to download. Defaults to 3.
            timeout (int, optional): timeout limit for downloading. Defaults to 15.

        Returns:
            list: list of PDF saved path.
        """
        os.makedirs(self.mineru_dir, exist_ok=True)

        # Progress bar for downloads
        tbar = TqdmLoggingWrapper(tqdm(total=len(batch_task_dict), desc="Downloading MinerU results", ncols=120))
        try:
            for file_path, mineru_dict in batch_task_dict.items():
                mineru_url = mineru_dict.get("mineru_result_url", "")

                if not mineru_url:
                    logger.warning(f"No mineru_result_url for {file_path}, skipping.")
                    batch_task_dict[file_path]["mineru_result_path"] = ""
                    tbar.update(1)
                    continue

                # determine filenames
                file_name = os.path.basename(mineru_url.split("/")[-1])
                final_path = os.path.join(self.mineru_dir, file_name)
                temp_path = final_path + ".part"

                # skip if already present
                if os.path.isfile(final_path):
                    logger.info(f"{final_path} already exists.")
                    batch_task_dict[file_path]["mineru_result_path"] = final_path
                    try:
                        tbar.set_postfix(file=os.path.basename(file_path), status="exists")
                    except Exception:
                        pass
                    tbar.update(1)
                    continue

                # try downloading with requests stream
                success = False
                last_err = None
                for attempt in range(1, num_tries + 1):
                    try:
                        with requests.get(mineru_url, stream=True, timeout=timeout, verify=True) as r:
                            r.raise_for_status()
                            # write to temp file
                            with open(temp_path, "wb") as f:
                                for chunk in r.iter_content(chunk_size=8192):
                                    if chunk:
                                        f.write(chunk)
                        # atomic move
                        os.replace(temp_path, final_path)
                        batch_task_dict[file_path]["mineru_result_path"] = os.path.abspath(final_path)
                        success = True
                        status = f"downloaded(attempt {attempt})"
                        break
                    except requests.RequestException as e:
                        last_err = e
                        logger.warning(f"Download attempt {attempt} failed for {mineru_url}: {e}")
                        # remove temp file if exists
                        try:
                            if os.path.exists(temp_path):
                                os.remove(temp_path)
                        except Exception:
                            pass
                        time.sleep(1)
                    except OSError as e:
                        last_err = e
                        logger.error(f"Filesystem error while writing {temp_path}: {e}")
                        try:
                            if os.path.exists(temp_path):
                                os.remove(temp_path)
                        except Exception:
                            pass
                        break

                if not success:
                    logger.error(f"Failed to download {mineru_url} after {num_tries} attempts. Last error: {last_err}")
                    batch_task_dict[file_path]["mineru_result_path"] = ""
                    status = "failed"

                # update progress bar with filename and status
                try:
                    tbar.set_postfix(file=os.path.basename(file_path), status=status)
                except Exception:
                    pass
                tbar.update(1)

        finally:
            tbar.close()

        return batch_task_dict

    def process_mineru_result(self, batch_task_dict, pdf_type="normal"):
        """Process MinerU results by extracting data, converting to middle JSON, and generating markdown.

        Args:
            batch_task_dict (dict): Dictionary containing batch task information and file paths.
            pdf_type (str, optional): Type of PDF being processed, e.g., "normal" or "scholar". Defaults to "normal".

        Returns:
            dict: Updated batch task dictionary with processed results.
        """
        # Add a progress bar to show per-file processing progress and status
        tbar = TqdmLoggingWrapper(tqdm(total=len(batch_task_dict), desc="Processing MinerU results", ncols=120))
        try:
            for file_name, file_info_dict in batch_task_dict.items():
                status = "skipped"
                try:
                    file_path = os.path.join(self.pdf_dir, file_name)
                    mineru_result_path = file_info_dict.get("mineru_result_path", "")
                    if not mineru_result_path or not os.path.isfile(mineru_result_path):
                        logger.warning(f"mineru result missing for {file_name}, skipping.")
                        batch_task_dict[file_name]["processed"] = False
                        status = "skipped"
                        continue
                    # extract the zip file to the original pdf name
                    extract_path = extract_zip_to_named_folder(mineru_result_path, self.mineru_dir)
                    mineru_pdf_name = os.path.basename(glob(os.path.join(extract_path, "*_origin.pdf"))[0]).split(
                        "_origin"
                    )[0]
                    
                    shutil.copy2(
                        file_path, os.path.join(extract_path, file_name)
                    )  # copy original PDF file to minerU directory

                    file_info_dict["file_path"] = os.path.join(extract_path, file_name)
                    origin_pdf_path = os.path.join(extract_path, file_name)

                    if self.llm_aid and not os.path.isfile(os.path.join(extract_path, f"{mineru_pdf_name}.md")):
                        image_list, pdf_doc = load_images_from_pdf(
                            convert_pdf_bytes_to_bytes_by_pypdfium2(read_fn(os.path.join(origin_pdf_path))),
                            image_type=ImageType.PIL,
                        )
                        image_dir = os.path.join(extract_path, "images")
                        md_writer, image_writer = FileBasedDataWriter(extract_path), FileBasedDataWriter(image_dir)
                        with open(glob(os.path.join(extract_path, "*_model.json"))[0]) as fr:
                            model_json = json.load(fr)
                        # LLM update header levels
                        middle_json = result_to_middle_json(
                            model_json,
                            image_list,
                            pdf_doc,
                            image_writer,
                            llm_aid=self.llm_aid,
                            llm_aided_config=self.llm_client_config,
                        )  # model_json to middle_json with llm

                        # json to markdown
                        make_func = pipeline_union_make if self.mineru_is_pipeline else vlm_union_make
                        markdown_content = make_func(middle_json["pdf_info"], MakeMode.MM_MD, image_dir)
                        # replace image_paths to relative paths
                        markdown_content = markdown_content.replace(image_dir, "images")
                        md_writer.write_string(f"{mineru_pdf_name}.md", markdown_content)
                        # TODO: convert markdown to paper components if pdf_type is scholar
                        if pdf_type == "scholar":
                            # extract metadata: title, DOI, references
                            pass
                    
                    batch_task_dict[file_name]["processed"] = True
                    status = "done"
                except Exception as e:
                    logger.exception(f"Error processing {file_name}: {e}")
                    batch_task_dict[file_name]["processed"] = False
                    status = "failed"
                finally:
                    # update progress bar for this file
                    try:
                        tbar.set_postfix(file=os.path.basename(file_path), status=status)
                    except Exception:
                        pass
                    tbar.update(1)
        finally:
            tbar.close()
        
        for file_name, file_info_dict in batch_task_dict.items():
            file_path = os.path.join(self.pdf_dir, file_name)
            if batch_task_dict[file_name]["processed"]:
                # rename the folder to a new name
                mineru_result_path = file_info_dict.get("mineru_result_path", "")
                zip_base = os.path.basename(mineru_result_path)
                unzip_name, _ = os.path.splitext(zip_base)
                new_folder_name = file_name.replace('.pdf', '')
                old_path = os.path.join(self.mineru_dir, unzip_name)
                new_path = os.path.join(self.mineru_dir, new_folder_name)
                if os.path.exists(old_path):
                    if not os.path.exists(new_path):
                        try:
                            os.rename(old_path, new_path)
                        except OSError as e:
                            logger.warning(f"Failed to rename {old_path} to {new_path}: {e}")
                    else:
                        # remove the new path and rename the old path
                        shutil.rmtree(new_path)
                        try:
                            os.rename(old_path, new_path)
                        except OSError as e:
                            logger.warning(f"Failed to rename {old_path} to {new_path}: {e}")
                        logger.warning(f"Target folder {new_folder_name} already exists, removing and renaming.")
                else:
                    logger.error(f"Source folder {old_path} does not exist, please check if the unzip is successful.")

                # rename the zip file to a new name
                if os.path.exists(mineru_result_path):
                    new_zip_name = file_name.replace('.pdf', '.zip')
                    new_zip_path = os.path.join(self.mineru_dir, new_zip_name)
                    if not os.path.exists(new_zip_path):
                        try:
                            os.rename(mineru_result_path, new_zip_path)
                        except OSError as e:
                            logger.warning(f"Failed to rename {mineru_result_path} to {new_zip_path}: {e}")
                    else:
                        logger.warning(f"Zip file {new_zip_name} already exists, skipping rename.")

        return batch_task_dict

    def process_local_pdfs(
        self,
        pdf_files=None,
        process_all=False,
        output_dir=None,
        max_retries=3,
        continue_on_error=True,
        model_version="vlm",
        language="en",
        is_ocr=True,
    ):
        """End-to-end processing of local PDF files.

        Pipeline:
        1. Collect PDF files from data/
        2. Upload to MinerU (batch)
        3. Poll for completion (with timeout)
        4. Download results (ZIP files)
        5. Extract and LLM-enhance markdown
        6. Move to output/ directory

        Args:
            pdf_files (list): List of PDF filenames to process (relative to pdf_dir)
            process_all (bool): Process all PDFs in pdf_dir
            output_dir (str): Output directory (defaults to self.mineru_dir)
            max_retries (int): Maximum retry attempts for failed operations
            continue_on_error (bool): Continue processing remaining files on error
            model_version (str): MinerU model version ("vlm" or "pipeline")
            language (str): Language for OCR
            is_ocr (bool): Enable OCR

        Returns:
            dict: Processing summary with success/failure counts and details
        """
        # 1. Input validation and PDF file collection
        if process_all:
            pdf_files = [os.path.basename(f) for f in glob(os.path.join(self.pdf_dir, "*.pdf"))]
        elif not pdf_files:
            raise ValueError("Must specify either pdf_files or process_all=True")

        if not pdf_files:
            logger.warning("No PDF files found to process")
            return {"total": 0, "successful": 0, "failed": 0, "errors": []}

        # 2. Create temporary subdirectory for this batch
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        batch_pdf_dir = os.path.join(self.pdf_dir, f"batch_{timestamp}")
        os.makedirs(batch_pdf_dir, exist_ok=True)
        output_dir = output_dir or self.mineru_dir
        os.makedirs(output_dir, exist_ok=True)

        # 3. Create symlinks to selected PDFs in batch directory
        for pdf_file in pdf_files:
            src = os.path.join(self.pdf_dir, pdf_file)
            dst = os.path.join(batch_pdf_dir, pdf_file)
            if os.path.exists(src):
                try:
                    os.symlink(os.path.abspath(src), dst)
                except OSError:
                    # Fallback to copy if symlink fails (e.g., on Windows)
                    shutil.copy2(src, dst)
            else:
                logger.warning(f"PDF file not found: {src}")

        # Initialize results tracking
        results = {"total": len(pdf_files), "successful": 0, "failed": 0, "errors": []}

        try:
            # Phase 1: Upload
            logger.info(f"[Phase 1/4] Uploading {len(pdf_files)} PDFs to MinerU...")
            batch_task_dict = None
            for attempt in range(max_retries):
                try:
                    batch_task_dict = self.upload_mineru_batch_task(
                        pdf_dir=batch_pdf_dir, model_version=model_version, language=language, is_ocr=is_ocr
                    )
                    break
                except Exception as e:
                    if attempt == max_retries - 1:
                        raise
                    logger.warning(f"Upload retry {attempt + 1}/{max_retries}: {e}")
                    time.sleep(2 ** attempt)  # Exponential backoff

            if not batch_task_dict:
                raise Exception("Failed to upload PDFs to MinerU")

            # Phase 2: Poll for completion
            logger.info("[Phase 2/4] Polling for task completion...")
            for batch_id, task_dict in batch_task_dict.items():
                for attempt in range(max_retries):
                    try:
                        task_dict = self.get_mineru_task_status(batch_id, task_dict)
                        batch_task_dict[batch_id] = task_dict
                        break
                    except Exception as e:
                        if attempt == max_retries - 1:
                            if not continue_on_error:
                                raise
                            logger.error(f"Polling failed after {max_retries} attempts: {e}")
                            results["errors"].append({"phase": "poll", "batch_id": batch_id, "error": str(e)})
                        else:
                            logger.warning(f"Poll retry {attempt + 1}/{max_retries}: {e}")
                            time.sleep(5)

            # Phase 3: Download results
            logger.info("[Phase 3/4] Downloading MinerU results...")
            for batch_id, task_dict in batch_task_dict.items():
                for attempt in range(max_retries):
                    try:
                        task_dict = self.download_mineru_results(task_dict, num_tries=max_retries)
                        batch_task_dict[batch_id] = task_dict
                        break
                    except Exception as e:
                        if attempt == max_retries - 1:
                            if not continue_on_error:
                                raise
                            logger.error(f"Download failed after {max_retries} attempts: {e}")
                            results["errors"].append({"phase": "download", "batch_id": batch_id, "error": str(e)})
                        else:
                            logger.warning(f"Download retry {attempt + 1}/{max_retries}: {e}")
                            time.sleep(2 ** attempt)

            # Phase 4: Extract and enhance
            logger.info("[Phase 4/4] Extracting and enhancing results...")
            # final_output = os.path.join(output_dir, f"results_{timestamp}")
            # os.makedirs(final_output, exist_ok=True)

            for batch_id, task_dict in batch_task_dict.items():
                try:
                    # Process each MinerU batch once. process_mineru_result already
                    # iterates over every file in task_dict and records per-file status.
                    task_dict = self.process_mineru_result(task_dict, pdf_type="normal")
                    batch_task_dict[batch_id] = task_dict

                    for file_path, file_info in task_dict.items():
                        if file_info.get("processed"):
                            results["successful"] += 1
                        else:
                            results["failed"] += 1
                            results["errors"].append(
                                {
                                    "file": file_path,
                                    "error": "MinerU result missing or post-processing failed",
                                }
                            )

                    # Move extracted session to final output directory
                    # if "mineru_result_path" in file_info:
                    #     extract_path = extract_zip_to_named_folder(file_info["mineru_result_path"], final_output)
                    #     logger.info(f"✓ Extracted to: {extract_path}")

                except Exception as e:
                    results["failed"] += len(task_dict)
                    error_info = {"phase": "process", "batch_id": batch_id, "error": str(e)}
                    results["errors"].append(error_info)
                    logger.error(f"Failed to process batch {batch_id}: {e}")

                    if not continue_on_error:
                        raise

            results["output_dir"] = self.mineru_dir
            logger.info(f"✓ Processing complete: {results['successful']}/{results['total']} successful")
            logger.info(f"✓ Results saved to: {self.mineru_dir}")

        except Exception as e:
            logger.exception(f"Pipeline failed: {e}")
            results["error"] = str(e)
            if not continue_on_error:
                raise

        finally:
            # Cleanup temp directory
            if os.path.exists(batch_pdf_dir):
                try:
                    shutil.rmtree(batch_pdf_dir)
                    logger.debug(f"Cleaned up temp directory: {batch_pdf_dir}")
                except Exception as e:
                    logger.warning(f"Failed to cleanup temp directory: {e}")

        return results


def parse_args():
    """Parse command-line arguments for the paper processor.

    Returns:
        argparse.Namespace: Parsed arguments containing options for downloading, parsing, and processing papers.
    """
    parser = argparse.ArgumentParser(description="Academic papar manager. Download, Parse, Extract metadata")
    # arguments for paper downloading, input DOIs
    parser.add_argument("--download_pdf", action="store_true", default=False, help="Whether to download PDFs")
    parser.add_argument("--dois", nargs="+", default=list(), help="list of target DOIs.")
    parser.add_argument("--doi-list", type=str, default=None, help="path to target paper DOIs.")
    parser.add_argument("--pdf-dir", type=str, default=None, help="directory path storing PDF files.")

    # arguments for paper processing
    parser.add_argument("--parse", action="store_true", default=False, help="Whether to run pdf parsing with MinerU")
    parser.add_argument("--mineru-dir", type=str, default="", help="directory to store MinerU result.")
    parser.add_argument("--mineru-task-log", type=str, default=None, help="path to mineru task log")
    parser.add_argument(
        "--mineru-mode",
        type=str,
        default="api",
        choices=("pipeline", "vlm", "api"),
        help="MinerU running mode. api = MinerU cloud API; pipeline/vlm = local run",
    )
    parser.add_argument("--is-ocr", type=bool, default=True, help="MinerU settings: is_ocr, default to be True")
    parser.add_argument("--language", type=str, default="en", help="MinerU settings: language, default to be 'en'")
    parser.add_argument(
        "--download-mineru", action="store_true", default=False, help="Whether to download mineru parsed result"
    )

    # arguments for extract metadata
    parser.add_argument(
        "--llm-aid",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="whether to use LLM to optimize title levels. Default Action: True; Model: Qwen3-235B",
    )
    parser.add_argument("--metadata", action="store_true", default=False, help="Whether to extract metadata")

    args = parser.parse_args()
    return args


if __name__ == "__main__":
    args = parse_args()
    logger.info(json.dumps(vars(args), indent=4))
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    paper_processor = PaperProcessor(
        pdf_dir=args.pdf_dir,
        mineru_dir=args.mineru_dir,
        llm_aid=args.llm_aid,
    )

    # Download PDF files with DOI list
    if args.download_pdf:
        logger.info("Start downloading papers with DOIs...")
        if len(args.dois) > 0:
            doi_list = args.dois
        elif args.doi_list and os.path.isfile(args.doi_list):
            with open(args.doi_list) as fr:
                doi_lines = fr.readlines()
            doi_list = [doi_line.strip() for doi_line in doi_lines]
        logger.info(f"{len(doi_list)} DOIs found to process.")
        success_doi_list = paper_processor.download_pdf(doi_list)

        with open(os.path.join(LOG_DIR, f"success_DOIs_{timestamp}.txt"), "w") as fw:
            for doi in success_doi_list:
                fw.write(f"{doi}\n")

    # Upload local files to MinerU Server
    mineru_task_dict = None
    if args.parse:
        logger.info("Start uploading papers to parse...")
        mineru_task_dict = paper_processor.upload_mineru_batch_task()

        # for file_path
        with open(os.path.join(LOG_DIR, f"mineru_task_log_{timestamp}.json"), "w") as fw:
            json.dump(mineru_task_dict, fw, indent=4)

    # Download & Process MinerU results
    if args.download_mineru:
        if mineru_task_dict is None:
            if os.path.isfile(args.mineru_task_log):
                with open(args.mineru_task_log) as fr:
                    mineru_task_dict = json.load(fr)
            else:
                logger.error("No mineru task info for downloading.")

        os.makedirs(args.mineru_dir, exist_ok=True)

        for batch_id, batch_task_dict in mineru_task_dict.items():
            batch_task_dict = paper_processor.get_mineru_task_status(batch_id, batch_task_dict)
            batch_task_dict = paper_processor.download_mineru_results(batch_task_dict)
            batch_task_dict = paper_processor.process_mineru_result(batch_task_dict)  # unzip & copy origin file
            mineru_task_dict[batch_id] = batch_task_dict

    if mineru_task_dict is not None:
        # for file_path
        with open(os.path.join(LOG_DIR, f"mineru_task_log_{timestamp}.json"), "w") as fw:
            json.dump(mineru_task_dict, fw, indent=4)
