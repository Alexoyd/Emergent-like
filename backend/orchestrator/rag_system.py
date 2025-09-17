import os
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer
import json
import hashlib

logger = logging.getLogger(__name__)

class RAGSystem:
    def __init__(self):
        self.model = None
        self.index = None
        self.documents = []
        self.document_metadata = []
        self.embeddings_cache = {}
        self.model_name = "all-MiniLM-L6-v2"  # Lightweight model
        self.initialized = False
    
    async def initialize(self):
        """Initialize the RAG system"""
        try:
            if self.initialized:
                return
            
            logger.info("Initializing RAG system...")
            self.model = SentenceTransformer(self.model_name)
            
            # Create FAISS index (384 dimensions for all-MiniLM-L6-v2)
            self.index = faiss.IndexFlatIP(384)
            
            # Load framework documentation if available
            await self._load_framework_docs()
            
            self.initialized = True
            logger.info("RAG system initialized successfully")
            
        except Exception as e:
            logger.error(f"Error initializing RAG system: {e}")
            self.initialized = False
    
    async def index_project(self, project_path: str) -> int:
        """Index a project's files for RAG"""
        try:
            if not self.initialized:
                await self.initialize()
            
            if not self.initialized:
                return 0
            
            project_path = Path(project_path)
            if not project_path.exists():
                logger.warning(f"Project path does not exist: {project_path}")
                return 0
            
            indexed_count = 0
            
            # Index relevant files
            for file_path in self._get_indexable_files(project_path):
                try:
                    content = self._read_file_content(file_path)
                    if content:
                        chunks = self._chunk_content(content, file_path)
                        await self._add_chunks_to_index(chunks, file_path)
                        indexed_count += len(chunks)
                        
                except Exception as e:
                    logger.warning(f"Error indexing file {file_path}: {e}")
                    continue
            
            logger.info(f"Indexed {indexed_count} chunks from project {project_path}")
            return indexed_count
            
        except Exception as e:
            logger.error(f"Error indexing project: {e}")
            return 0
    
    async def get_relevant_context(self, query: str, max_chunks: int = 5) -> str:
        """Get relevant context for a query"""
        try:
            if not self.initialized or self.index.ntotal == 0:
                return ""
            
            # Generate query embedding
            query_embedding = self.model.encode([query])
            
            # Search for similar chunks
            scores, indices = self.index.search(query_embedding, min(max_chunks, self.index.ntotal))
            
            relevant_chunks = []
            for score, idx in zip(scores[0], indices[0]):
                if idx < len(self.documents) and score > 0.3:  # Similarity threshold
                    chunk = self.documents[idx]
                    metadata = self.document_metadata[idx]
                    relevant_chunks.append({
                        "content": chunk,
                        "file": metadata.get("file_path", "unknown"),
                        "score": float(score)
                    })
            
            # Format context
            if not relevant_chunks:
                return ""
            
            context_parts = []
            for chunk in relevant_chunks:
                context_parts.append(f"From {chunk['file']}:\n{chunk['content']}\n")
            
            return "\n".join(context_parts)
            
        except Exception as e:
            logger.error(f"Error getting relevant context: {e}")
            return ""
    
    async def add_documentation(self, doc_content: str, doc_name: str) -> bool:
        """Add documentation to the index"""
        try:
            if not self.initialized:
                await self.initialize()
            
            if not self.initialized:
                return False
            
            chunks = self._chunk_content(doc_content, doc_name)
            await self._add_chunks_to_index(chunks, doc_name)
            
            logger.info(f"Added {len(chunks)} documentation chunks for {doc_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error adding documentation: {e}")
            return False
    
    def _get_indexable_files(self, project_path: Path) -> List[Path]:
        """Get list of files that should be indexed"""
        indexable_extensions = {
            '.php', '.js', '.ts', '.jsx', '.tsx', '.vue', '.py', 
            '.md', '.txt', '.json', '.yaml', '.yml', '.env.example',
            '.blade.php', '.twig'
        }
        
        ignore_dirs = {
            'node_modules', 'vendor', '.git', 'storage', 'bootstrap/cache',
            'public/storage', '.next', 'dist', 'build', '__pycache__'
        }
        
        indexable_files = []
        
        for file_path in project_path.rglob('*'):
            if not file_path.is_file():
                continue
            
            # Skip ignored directories
            if any(ignore_dir in file_path.parts for ignore_dir in ignore_dirs):
                continue
            
            # Check extension
            if file_path.suffix.lower() in indexable_extensions:
                indexable_files.append(file_path)
            
            # Special files without extensions
            if file_path.name.lower() in {'readme', 'makefile', 'dockerfile', 'composer.json', 'package.json'}:
                indexable_files.append(file_path)
        
        return indexable_files[:100]  # Limit to prevent overload
    
    def _read_file_content(self, file_path: Path) -> Optional[str]:
        """Read file content safely"""
        try:
            # Skip large files
            if file_path.stat().st_size > 1024 * 1024:  # 1MB limit
                return None
            
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()
                
        except Exception as e:
            logger.warning(f"Could not read file {file_path}: {e}")
            return None
    
    def _chunk_content(self, content: str, source: str) -> List[Dict[str, Any]]:
        """Split content into chunks for embedding"""
        max_chunk_size = 500  # Characters
        overlap = 50
        
        chunks = []
        
        # Split by lines first
        lines = content.split('\n')
        current_chunk = ""
        
        for line in lines:
            if len(current_chunk) + len(line) > max_chunk_size and current_chunk:
                # Create chunk
                chunks.append({
                    "content": current_chunk.strip(),
                    "source": source,
                    "type": self._detect_content_type(current_chunk)
                })
                
                # Start new chunk with overlap
                if len(current_chunk) > overlap:
                    current_chunk = current_chunk[-overlap:] + "\n" + line
                else:
                    current_chunk = line
            else:
                current_chunk += "\n" + line if current_chunk else line
        
        # Add final chunk
        if current_chunk.strip():
            chunks.append({
                "content": current_chunk.strip(),
                "source": source,
                "type": self._detect_content_type(current_chunk)
            })
        
        return chunks
    
    def _detect_content_type(self, content: str) -> str:
        """Detect the type of content"""
        content_lower = content.lower()
        
        if any(keyword in content_lower for keyword in ['function', 'class', 'method', 'def ', 'public ', 'private ']):
            return "code"
        elif any(keyword in content_lower for keyword in ['test', 'spec', 'describe', 'it(']):
            return "test"  
        elif any(keyword in content_lower for keyword in ['#', 'readme', 'documentation']):
            return "documentation"
        elif any(keyword in content_lower for keyword in ['config', 'setting', 'env']):
            return "configuration"
        else:
            return "general"
    
    async def _add_chunks_to_index(self, chunks: List[Dict[str, Any]], source: str):
        """Add chunks to the FAISS index"""
        try:
            if not chunks:
                return
            
            # Extract content for embedding
            texts = [chunk["content"] for chunk in chunks]
            
            # Generate embeddings
            embeddings = self.model.encode(texts)
            
            # Normalize embeddings for cosine similarity
            embeddings = embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)
            
            # Add to index
            self.index.add(embeddings.astype('float32'))
            
            # Store documents and metadata
            for i, chunk in enumerate(chunks):
                self.documents.append(chunk["content"])
                self.document_metadata.append({
                    "file_path": source,
                    "content_type": chunk["type"],
                    "chunk_index": i
                })
                
        except Exception as e:
            logger.error(f"Error adding chunks to index: {e}")
    
    async def _load_framework_docs(self):
        """Load framework documentation if available"""
        try:
            docs_dir = Path(__file__).parent.parent / "docs"
            if not docs_dir.exists():
                return
            
            for doc_file in docs_dir.glob("*.md"):
                try:
                    content = doc_file.read_text(encoding='utf-8')
                    await self.add_documentation(content, doc_file.name)
                except Exception as e:
                    logger.warning(f"Could not load doc file {doc_file}: {e}")
                    
        except Exception as e:
            logger.warning(f"Could not load framework docs: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get RAG system statistics"""
        return {
            "initialized": self.initialized,
            "total_documents": len(self.documents),
            "index_size": self.index.ntotal if self.index else 0,
            "model_name": self.model_name
        }
    
    async def clear_index(self):
        """Clear the entire index"""
        try:
            if self.index:
                self.index.reset()
            self.documents.clear()
            self.document_metadata.clear()
            self.embeddings_cache.clear()
            
            logger.info("RAG index cleared")
            
        except Exception as e:
            logger.error(f"Error clearing index: {e}")