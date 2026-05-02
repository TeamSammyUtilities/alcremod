import os
import shutil

def clear_pycache(root_dir: str):

    removed_count = 0

    for dirpath, dirnames, filenames in os.walk(root_dir):
        if "__pycache__" in dirnames:
            cache_path = os.path.join(dirpath, "__pycache__")
            try:
                shutil.rmtree(cache_path)
                removed_count += 1
                print(f"Removed: {cache_path}")
            except Exception as e:
                print(f"Failed to remove {cache_path}: {e}")

            dirnames.remove("__pycache__")

    print(f"Done. Total __pycache__ folders removed: {removed_count}")


if __name__ == "__main__":
    clear_pycache(".")