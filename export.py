import requests, json, os, zipfile
from requests.exceptions import ReadTimeout, ConnectionError, RequestException
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

TIMEOUT = (10, 60)
FAIL_LOG = "failed_downloads.txt"

def log_failure(count,link,reason):
    with open(FAIL_LOG,"a",encoding="utf-8") as f:
        f.write(f"{count}\t{reason}\t{link}\n")
        print(f"Successfully added {link} to failure log.")

def dealZips(path, extractDir, count, link):
    if os.path.exists(extractDir):
        print(f"Already extracted: {extractDir}, skipping")
        os.remove(path)
        return
    
    os.makedirs(extractDir, exist_ok=True)
    try:
        with zipfile.ZipFile(path, "r") as z:
            for member in z.infolist():
                targetPath = os.path.abspath(os.path.join(extractDir, member.filename))
                if not targetPath.startswith(os.path.abspath(extractDir) + os.sep):
                    raise ValueError(f"Unsafe zip entry detected: {member.filename}")
            z.extractall(extractDir)
    except Exception as e:
        log_failure(count, link, f"zip_extract_error:{e}")
        return
    finally:
        if os.path.exists(path):
            os.remove(path)
        print(f"Successfully unzipped: {path}")
        
def main():
    typeMap = {
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/png": ".png",
        "video/mp4": ".mp4",
        "application/zip": ".zip",
    }

    outputDirectory = "memories"
    dataFile = "memories_history.json"

    os.makedirs(outputDirectory, exist_ok=True)

    open(FAIL_LOG, "w", encoding="utf-8").close() 

    retry = Retry(
    total=3,
    connect=3,
    read=3,
    backoff_factor=1.0,  
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["GET"],
    raise_on_status=False,
    )

    adapter = HTTPAdapter(max_retries=retry)

    session = requests.Session()
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    with open(dataFile) as jsonFile:
        data = json.load(jsonFile)
        saved = data["Saved Media"]

        print(f"{len(saved)} Files detected. ")

        count = 0
        for memory in saved:
            count += 1
            link = memory["Media Download Url"]
            date = memory["Date"]
            safeDate = (
                date.replace(" ", "_")
                    .replace(":", "-")
            )
            fileName = str(safeDate) + " " + str(count)
            try:
                with session.get(link, stream=True, timeout=TIMEOUT) as file:
                    file.raise_for_status()

                    contentType = file.headers.get("Content-Type", "").lower()
                    if contentType not in typeMap:
                        print(f"Wrong file type detected, {contentType} - skipping file {count}")
                        continue

                    ext = typeMap[contentType]
                    outName = fileName + ext
                    outputPath = os.path.join(outputDirectory, outName)

                    if os.path.exists(outputPath):
                        print(f"Already exists, skipping: {outputPath}")
                        continue

                    with open(outputPath, "wb") as outFile:
                        for chunk in file.iter_content(chunk_size=8192):
                            if chunk:
                                outFile.write(chunk)

                    print(f"Saved: {outputPath}")

                    if ext == ".zip":
                        print("Zip found, unzipping")
                        extractDirectory = os.path.join(outputDirectory, fileName)
                        dealZips(outputPath, extractDirectory, count, link)

            except ReadTimeout:
                print(f"Read timeout for file {count}, skipping")
                log_failure(count,link, "Read Timeout")
                continue

            except ConnectionError:
                print(f"Connection error for file {count}, skipping")
                log_failure(count,link, "Connection Timeout")
                continue

            except RequestException as e:
                print(f"Request failed for file {count}: {e}")
                log_failure(count,link, "Request Timeout")
                continue


if __name__ == "__main__":
    main()