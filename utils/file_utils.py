import os
import shutil
from pathlib import Path
from typing import List
PathLike = str

def find_files(directory: PathLike, extension: PathLike) -> List[str]:
    """
    Busca recursivamente todos os arquivos com uma extensão específica em um diretório.
    
    Args:
        directory: Caminho do diretório onde buscar arquivos
        extension: Extensão do arquivo (ex: '.pdf', '.docx')
    
    Returns:
        Lista de caminhos completos dos arquivos encontrados
    """
    file_paths: List[str] = []
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith(extension):
                file_paths.append(os.path.join(root, file))
    return file_paths

def move_file_to_processed(file_path: str, output_directory: str) -> bool:
    """
    Move um arquivo processado para o diretório de concluídos.
    
    Esta função é usada para sinalizar ao usuário que um arquivo já foi processado,
    movendo-o da pasta de entrada (A Fazer) para a pasta de concluídos (Feito).
    
    Args:
        file_path: Caminho completo do arquivo a ser movido
        output_directory: Diretório de destino onde o arquivo será movido
    
    Returns:
        True se o arquivo foi movido com sucesso, False caso contrário
    
    Raises:
        OSError: Se houver erro ao criar o diretório de destino ou mover o arquivo
    """
    try:
        # Converte para Path para facilitar manipulação
        source_path: Path = Path(file_path)
        
        # Verifica se o arquivo existe
        if not source_path.exists():
            return False
        
        # Cria o diretório de destino se não existir
        output_path: Path = Path(output_directory)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Define o caminho de destino mantendo o nome do arquivo
        destination_path: Path = output_path / source_path.name
        
        # Move o arquivo
        shutil.move(str(source_path), str(destination_path))
        
        return True
    except Exception as e:
        # Log do erro seria feito pelo chamador
        return False

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
