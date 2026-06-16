import os
import json
import re
from pypdf import PdfReader

class NativeRecursiveSplitter:
    """A native implementation of a recursive text splitter with overlap."""
    def __init__(self, chunk_size=3000, overlap=300):
        self.chunk_size = chunk_size
        self.overlap = overlap
        # Hierarchy of separators: Paragraphs -> Lines -> Sentences -> Words
        self.separators = ["\n\n", "\n", ". ", " "]

    def split_text(self, text: str) -> list:
        return self._split(text, self.separators)

    def _split(self, text: str, separators: list) -> list:
        if len(text) <= self.chunk_size:
            return [text]
            
        separator = separators[0] if separators else ""
        for sep in separators:
            if sep in text:
                separator = sep
                break
                
        splits = text.split(separator) if separator else list(text)
        
        chunks = []
        current_chunk = ""
        
        for split in splits:
            part = split + (separator if separator else "")
            if len(current_chunk) + len(part) > self.chunk_size and current_chunk:
                chunks.append(current_chunk.strip())
                # Create overlap by keeping the end of the previous chunk
                overlap_text = current_chunk[-self.overlap:] if self.overlap > 0 else ""
                current_chunk = overlap_text + part
            else:
                current_chunk += part
                
        if current_chunk:
            chunks.append(current_chunk.strip())
            
        return chunks

def extract_chunks(file_path: str, jurisdiction: str, doc_id: str) -> list:
    if not os.path.exists(file_path):
        return []
        
    print(f"📄 Recursively chunking: {os.path.basename(file_path)}")
    splitter = NativeRecursiveSplitter(chunk_size=3000, overlap=300)
    chunks = []
    
    if file_path.endswith('.txt'):
        with open(file_path, 'r', encoding='utf-8') as f:
            text = f.read()
            text_chunks = splitter.split_text(text)
            for i, chunk_text in enumerate(text_chunks):
                chunks.append({
                    "jurisdiction": jurisdiction,
                    "doc_id": doc_id,
                    "citation": f"Part {i + 1}",
                    "raw_text": chunk_text
                })
                
    elif file_path.endswith('.pdf'):
        try:
            reader = PdfReader(file_path)
            full_text = ""
            for page in reader.pages: # Read the whole PDF now
                full_text += page.extract_text() + "\n\n"
                
            text_chunks = splitter.split_text(full_text)
            for i, chunk_text in enumerate(text_chunks):
                chunks.append({
                    "jurisdiction": jurisdiction,
                    "doc_id": doc_id,
                    "citation": f"Chunk {i + 1}",
                    "raw_text": chunk_text
                })
        except Exception as e:
            print(f"❌ PDF Error: {e}")
            
    return chunks

if __name__ == "__main__":
    base_dir = "/Users/ryogeshwaran/workpace/regtech"
    documents = [
        {"path": f"{base_dir}/packs/in/source/rbi_kyc_master.pdf", "jur": "IN", "id": "rbi_kyc_2016"},
        {"path": f"{base_dir}/packs/intl/basel_iii/source/basel_iii_framework.pdf", "jur": "INTL", "id": "basel_iii_framework"},
        {"path": f"{base_dir}/packs/eu/source/mifid_ii_guide.pdf", "jur": "EU", "id": "mifid_ii_guide"},
        {"path": f"{base_dir}/packs/in/source/rbi_op_guidelines_primary_dealers.pdf", "jur": "IN", "id": "rbi_op_guidelines"},
        {"path": f"{base_dir}/packs/in/source/rbi_ReliefSavingsBonds.pdf", "jur": "IN", "id": "rbi_relief_bonds"}
    ]
    
    output_dir = f"{base_dir}/data/processed_json"
    os.makedirs(output_dir, exist_ok=True)
    
    for doc in documents:
        data = extract_chunks(doc["path"], doc["jur"], doc["id"])
        if data:
            with open(f"{output_dir}/{doc['id']}_chunks.json", "w") as f:
                json.dump(data, f, indent=2)
            print(f"✅ Created {len(data)} overlapping chunks -> {doc['id']}_chunks.json")