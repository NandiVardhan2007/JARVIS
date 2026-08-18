"""
Test suite for Document Retrieval-Augmented Generation (RAG) Engine and Tools.
"""

import os
import tempfile
import json
import csv
from pathlib import Path
from vision.memory.rag_engine import DocumentRAGEngine, rag_engine, search_and_read_documents, search_documents_in_directory, summarize_document


def test_rag_chunking_and_bm25_ranking():
    engine = DocumentRAGEngine()

    text = (
        "Quantum computing is a rapidly-emerging technology that harnesses the laws of quantum mechanics "
        "to solve problems too complex for classical computers. Superconducting qubits are one common approach.\n\n"
        "Machine learning algorithms utilize statistical techniques to give computer systems the ability to learn from data. "
        "Deep neural networks have achieved state of the art results in vision and natural language processing.\n\n"
        "Astrophysics is a branch of space science that applies the laws of physics and chemistry to explain the birth, "
        "life and death of stars, planets, galaxies, nebulae and other objects in the universe."
    )

    chunks = engine.chunk_text(text, chunk_size=50, overlap=10, preserve_paragraphs=True)
    assert len(chunks) >= 3

    # Test BM25 ranking for machine learning
    ranked_ml = engine.rank_passages_bm25(chunks, "deep neural networks learning from data", top_k=1)
    assert len(ranked_ml) == 1
    assert "Machine learning" in ranked_ml[0][1]["text"]

    # Test BM25 ranking for quantum
    ranked_quantum = engine.rank_passages_bm25(chunks, "quantum mechanics qubits", top_k=1)
    assert len(ranked_quantum) == 1
    assert "Quantum computing" in ranked_quantum[0][1]["text"]


def test_rag_multi_format_extraction():
    engine = DocumentRAGEngine()

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)

        # 1. Plain text / Markdown
        txt_file = tmp_path / "notes.md"
        txt_file.write_text("# Project Specifications\nThis is a critical document about autonomous AI engines.", encoding="utf-8")
        extracted_txt = engine.extract_text_from_file(txt_file)
        assert "autonomous AI engines" in extracted_txt

        # 2. JSON file
        json_file = tmp_path / "data.json"
        json_file.write_text(json.dumps({"project": "VISION", "version": "2.0", "status": "active"}), encoding="utf-8")
        extracted_json = engine.extract_text_from_file(json_file)
        assert '"project": "VISION"' in extracted_json

        # 3. CSV file
        csv_file = tmp_path / "records.csv"
        with open(csv_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Name", "Role", "City"])
            writer.writerow(["Nandu", "Lead Developer", "Anaparthi"])
        extracted_csv = engine.extract_text_from_file(csv_file)
        assert "Lead Developer" in extracted_csv

        # 4. Search in document
        search_res = engine.search_in_document(txt_file, "autonomous engines")
        assert "RAG Document Context" in search_res
        assert "autonomous AI engines" in search_res

        # 5. Search in directory
        dir_res = engine.search_in_directory(tmp_path, "Lead Developer Nandu")
        assert "Multi-Document RAG Results" in dir_res
        assert "records.csv" in dir_res

        # 6. Summarize document
        sum_res = engine.summarize_document(txt_file)
        assert "Document Summary" in sum_res
        assert "Project Specifications" in sum_res
