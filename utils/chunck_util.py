import re
from typing import List


def optimize_text(text: str) -> str:
    """
    Otimiza o texto removendo espaços duplos, quebras de linha desnecessárias
    e outros caracteres que aumentam o número de tokens sem valor.
    
    Isso reduz significativamente o custo de tokens na API da OpenAI.
    
    Args:
        text: Texto original
        
    Returns:
        Texto otimizado com menos tokens
    """
    if not text:
        return ""
    
    # Remove múltiplos espaços em branco
    text = re.sub(r' +', ' ', text)
    
    # Remove múltiplas quebras de linha (mantém no máximo 2)
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    # Remove espaços no início e fim de linhas
    text = re.sub(r' +(\n)', r'\1', text)
    text = re.sub(r'(\n) +', r'\1', text)
    
    # Remove caracteres de controle desnecessários
    text = re.sub(r'[\x00-\x08\x0b-\x0c\x0e-\x1f]', '', text)
    
    # Remove espaços antes de pontuação
    text = re.sub(r' +([.,;:!?])', r'\1', text)
    
    return text.strip()


def chunk_text(text: str, max_words: int = 5000) -> List[str]:  # AUMENTADO de 3000 para 5000 para reduzir número de chunks
    """
    Divide um texto em chunks de tamanho máximo especificado.
    
    Otimizado para documentos grandes (2000+ páginas):
    - Usa chunks maiores (5000 palavras) para reduzir número de chamadas à API e evitar rate limits
    - Mantém contexto preservado ao dividir por parágrafos quando possível
    
    Args:
        text: Texto a ser dividido
        max_words: Número máximo de palavras por chunk (padrão: 3000)
        
    Returns:
        Lista de chunks de texto
    """
    if not text:
        return []

    # Tenta dividir por parágrafos primeiro (mantém melhor contexto)
    paragraphs: List[str] = re.split(r'\n\s*\n', text)
    
    chunks: List[str] = []
    current_chunk: List[str] = []
    current_word_count: int = 0
    
    for paragraph in paragraphs:
        paragraph = paragraph.strip()
        if not paragraph:
            continue
            
        paragraph_words: int = len(paragraph.split())
        
        # Se o parágrafo sozinho excede o limite, divide por sentenças
        if paragraph_words > max_words:
            # Adiciona o chunk atual se houver
            if current_chunk:
                chunks.append('\n\n'.join(current_chunk))
                current_chunk = []
                current_word_count = 0
            
            # Divide o parágrafo grande por sentenças
            sentences: List[str] = re.split(r'([.!?]+\s+)', paragraph)
            sentence_chunk: List[str] = []
            sentence_word_count: int = 0
            
            for i in range(0, len(sentences), 2):
                if i + 1 < len(sentences):
                    sentence = sentences[i] + sentences[i + 1]
                else:
                    sentence = sentences[i]
                
                sentence_words: int = len(sentence.split())
                
                if sentence_word_count + sentence_words > max_words and sentence_chunk:
                    chunks.append(' '.join(sentence_chunk))
                    sentence_chunk = [sentence]
                    sentence_word_count = sentence_words
                else:
                    sentence_chunk.append(sentence)
                    sentence_word_count += sentence_words
            
            if sentence_chunk:
                chunks.append(' '.join(sentence_chunk))
        else:
            # Se adicionar este parágrafo exceder o limite, finaliza o chunk atual
            if current_word_count + paragraph_words > max_words and current_chunk:
                chunks.append('\n\n'.join(current_chunk))
                current_chunk = [paragraph]
                current_word_count = paragraph_words
            else:
                current_chunk.append(paragraph)
                current_word_count += paragraph_words
    
    # Adiciona o último chunk se houver
    if current_chunk:
        chunks.append('\n\n'.join(current_chunk))
    
    # Se não conseguiu dividir por parágrafos, divide por palavras simples
    if not chunks:
        words: List[str] = text.split()
        chunks = [
            " ".join(words[i:i + max_words])
            for i in range(0, len(words), max_words)
        ]
    
    return chunks