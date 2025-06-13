from typing import List

class TextSplitter:
    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200):
        if chunk_overlap >= chunk_size:
            raise ValueError("chunk_overlap must be smaller than chunk_size")
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def split_text(self, text: str) -> List[str]:
        raise NotImplementedError

    def create_documents(self, texts: List[str]) -> List[str]:
        docs: List[str] = []
        for text in texts:
            docs.extend(self.split_text(text))
        return docs

    def split_documents(self, docs: List[str]) -> List[str]:
        return self.create_documents(docs)

    def _join_docs(self, docs: List[str], separator: str) -> str | None:
        text = separator.join(docs).strip()
        return text if text else None

    def merge_splits(self, splits: List[str], separator: str) -> List[str]:
        docs: List[str] = []
        current: List[str] = []
        total = 0
        for d in splits:
            length = len(d)
            if total + length >= self.chunk_size:
                if total > self.chunk_size:
                    print(
                        f"Created a chunk of size {total}, which is longer than the specified {self.chunk_size}"
                    )
                if current:
                    doc = self._join_docs(current, separator)
                    if doc is not None:
                        docs.append(doc)
                    while total > self.chunk_overlap or (
                        total + length > self.chunk_size and total > 0
                    ):
                        total -= len(current[0])
                        current.pop(0)
            current.append(d)
            total += length
        doc = self._join_docs(current, separator)
        if doc is not None:
            docs.append(doc)
        return docs

class RecursiveCharacterTextSplitter(TextSplitter):
    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200, separators: List[str] | None = None):
        super().__init__(chunk_size, chunk_overlap)
        self.separators = separators or ["\n\n", "\n", ".", ",", ">", "<", " ", ""]

    def split_text(self, text: str) -> List[str]:
        if not text:
            return []

        separator = self.separators[-1]
        for s in self.separators:
            if s == "" or s in text:
                separator = s
                break

        splits = text.split(separator) if separator else list(text)

        final_chunks: List[str] = []
        good_splits: List[str] = []
        for s in splits:
            if len(s) < self.chunk_size:
                good_splits.append(s)
            else:
                if good_splits:
                    final_chunks.extend(self.merge_splits(good_splits, separator))
                    good_splits = []
                final_chunks.extend(self.split_text(s))
        if good_splits:
            final_chunks.extend(self.merge_splits(good_splits, separator))
        return final_chunks
