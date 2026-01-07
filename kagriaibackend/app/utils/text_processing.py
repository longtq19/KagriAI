import re
from typing import Generator, List

class SentenceBuffer:
    def __init__(self):
        self.buffer = ""
        # Regex for sentence endings: ., !, ?, or newlines, followed by space or end of string
        self.sentence_end_pattern = re.compile(r'(?<=[.!?\n])\s+')

    def add_token(self, token: str) -> List[str]:
        """
        Adds a token to the buffer and returns a list of completed sentences.
        """
        self.buffer += token
        sentences = []
        
        while True:
            match = self.sentence_end_pattern.search(self.buffer)
            if match:
                end_pos = match.end()
                sentence = self.buffer[:end_pos].strip()
                if sentence:
                    sentences.append(sentence)
                self.buffer = self.buffer[end_pos:]
            else:
                break
        
        return sentences

    def flush(self) -> str:
        """
        Returns the remaining content in the buffer as the final sentence.
        """
        remaining = self.buffer.strip()
        self.buffer = ""
        return remaining

def clean_text(text: str) -> str:
    """
    Basic text cleaning.
    """
    return text.strip()
