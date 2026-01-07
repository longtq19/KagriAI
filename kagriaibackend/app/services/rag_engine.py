import os
from typing import List
from langchain_community.document_loaders import DirectoryLoader, TextLoader
try:
    from langchain.text_splitter import RecursiveCharacterTextSplitter
except ImportError:
    from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from app.core.config import settings
import hashlib
import json

class RAGEngine:
    def __init__(self):
        self.vector_store = None
        self.embeddings = None
        self.meta_path = os.path.join(settings.VECTOR_STORE_PATH, "meta.json")
        self.manifest = {"files": {}}
        # Lazy initialization to avoid blocking server startup
        try:
            self.manifest = self._load_manifest()
        except Exception:
            self.manifest = {"files": {}}
    
    def ensure_initialized(self):
        if self.embeddings is None:
            self.embeddings = HuggingFaceEmbeddings(model_name=settings.EMBEDDING_MODEL)
        if self.vector_store is None:
            self.load_or_create_index()

    def load_or_create_index(self):
        if os.path.exists(os.path.join(settings.VECTOR_STORE_PATH, "index.faiss")):
            print("Loading existing vector store...")
            self.vector_store = FAISS.load_local(
                settings.VECTOR_STORE_PATH, 
                self.embeddings,
                allow_dangerous_deserialization=True
            )
        else:
            print("Vector store not found. Creating new one from docs...")
            self.build_index()
    
    def _load_manifest(self):
        try:
            with open(self.meta_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"files": {}}  # path -> sha1

    def build_index(self):
        if self.embeddings is None:
            self.embeddings = HuggingFaceEmbeddings(model_name=settings.EMBEDDING_MODEL)
        if not os.path.exists(settings.DOCS_PATH):
            os.makedirs(settings.DOCS_PATH)
            # Maybe trigger crawler here or warn
            print(f"No docs found in {settings.DOCS_PATH}. Index will be empty.")
            return

        loader = DirectoryLoader(settings.DOCS_PATH, glob="**/*.txt", loader_cls=TextLoader, loader_kwargs={"encoding": "utf-8"})
        documents = loader.load()
        
        if not documents:
            print("No documents to index.")
            return

        text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
        
        # Exclude docs that duplicate DB (products, company info)
        filtered_docs = []
        for doc in documents:
            src = doc.metadata.get("source", "")
            if "/products/" in src or src.endswith("infoCompany.txt"):
                continue
            filtered_docs.append(doc)
        
        if not filtered_docs:
            print("No eligible documents after filtering.")
            return
        
        # Compute hashes to detect new files
        docs_to_process = []
        for doc in filtered_docs:
            src = doc.metadata.get("source", "")
            try:
                with open(src, "rb") as f:
                    content = f.read()
                sha1 = hashlib.sha1(content).hexdigest()
            except Exception:
                sha1 = None
            prev_sha1 = self.manifest["files"].get(src)
            if sha1 and sha1 == prev_sha1:
                continue
            docs_to_process.append(doc)
        
        if not docs_to_process:
            print("No new documents to embed.")
            return
        
        texts = text_splitter.split_documents(docs_to_process)
        
        if self.vector_store:
            self.vector_store.add_documents(texts)
        else:
            self.vector_store = FAISS.from_documents(texts, self.embeddings)
        self.vector_store.save_local(settings.VECTOR_STORE_PATH)
        
        # Update manifest
        for doc in docs_to_process:
            src = doc.metadata.get("source", "")
            try:
                with open(src, "rb") as f:
                    content = f.read()
                sha1 = hashlib.sha1(content).hexdigest()
                self.manifest["files"][src] = sha1
            except Exception:
                pass
        try:
            os.makedirs(settings.VECTOR_STORE_PATH, exist_ok=True)
            with open(self.meta_path, "w", encoding="utf-8") as f:
                json.dump(self.manifest, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Failed to write manifest: {e}")
        
        print(f"Index updated with {len(texts)} new chunks.")

    def search(self, query: str, k: int = 3) -> List[str]:
        self.ensure_initialized()
        if not self.vector_store:
            return []
        
        docs = self.vector_store.similarity_search(query, k=k)
        return [doc.page_content for doc in docs]

    def search_with_score(self, query: str, k: int = 3):
        self.ensure_initialized()
        if not self.vector_store:
            return []
        return self.vector_store.similarity_search_with_score(query, k=k)
    
    def rebuild_index(self):
        """
        Force rebuild: remove existing index and manifest, then build from filtered docs.
        """
        try:
            faiss_path = os.path.join(settings.VECTOR_STORE_PATH, "index.faiss")
            pkl_path = os.path.join(settings.VECTOR_STORE_PATH, "index.pkl")
            if os.path.exists(faiss_path):
                os.remove(faiss_path)
            if os.path.exists(pkl_path):
                os.remove(pkl_path)
            if os.path.exists(self.meta_path):
                os.remove(self.meta_path)
            self.vector_store = None
            self.manifest = {"files": {}}
            print("Old vector store removed. Rebuilding...")
        except Exception as e:
            print(f"Failed to remove old index: {e}")
        self.build_index()

rag_engine = RAGEngine()
