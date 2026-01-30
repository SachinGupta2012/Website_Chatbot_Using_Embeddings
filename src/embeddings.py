from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.embeddings import HuggingFaceEmbeddings  # Updated import
from langchain_community.vectorstores import FAISS  # Updated import
from langchain_core.documents import Document
from typing import List, Dict
import hashlib
import os

class EmbeddingsManager:
    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2",
            model_kwargs={'device': 'cpu'},
            encode_kwargs={'normalize_embeddings': True}
        )
        self.vector_store = None
    
    def create_chunks(self, crawled_data: Dict) -> List[Document]:
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", ". ", "!", "?", ", ", " ", ""]
        )
        
        raw_chunks = text_splitter.split_text(crawled_data['content'])
        
        documents = []
        seen_hashes = set()
        
        for i, chunk in enumerate(raw_chunks):
            chunk = chunk.strip()
            if len(chunk) < 50:
                continue
            
            chunk_hash = hashlib.md5(chunk.encode()).hexdigest()
            if chunk_hash in seen_hashes:
                continue
            seen_hashes.add(chunk_hash)
            
            doc = Document(
                page_content=chunk,
                metadata={
                    'source_url': crawled_data['url'],
                    'page_title': crawled_data['title'],
                    'chunk_index': i
                }
            )
            documents.append(doc)
        
        return documents
    
    def create_vector_store(self, crawled_data: Dict, save_path: str = None) -> FAISS:
        documents = self.create_chunks(crawled_data)
        
        if not documents:
            raise ValueError("No valid chunks created")
        
        self.vector_store = FAISS.from_documents(documents, self.embeddings)
        
        if save_path:
            os.makedirs(save_path, exist_ok=True)
            self.vector_store.save_local(save_path)
        
        return self.vector_store
    
    def load_vector_store(self, path: str) -> FAISS:
        if not os.path.exists(path):
            raise FileNotFoundError(f"No index at {path}")
        self.vector_store = FAISS.load_local(
            path, 
            self.embeddings, 
            allow_dangerous_deserialization=True
        )
        return self.vector_store