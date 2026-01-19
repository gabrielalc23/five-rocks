import os
from typing import List
PathLike = str

def find_files(directory: PathLike, extension: PathLike) -> List[str]:
    file_paths: List[str] = []
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith(extension):
                file_paths.append(os.path.join(root, file))
    return file_paths

if __name__ == '__main__':

    project_root: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    data_dir: str = os.path.join(project_root, 'data')
    
    print(f"Procurando arquivos em: {data_dir}")
    
    pdf_files: List[str] = find_files(data_dir, '.pdf')

    print("\nArquivos .pdf encontrados:")

    for f in pdf_files:
        print(f"- {os.path.basename(f)}")

    docx_files: List[str] = find_files(data_dir, '.docx')

    print("\nArquivos .docx encontrados:")

    for f in docx_files:
        print(f"- {os.path.basename(f)}")
