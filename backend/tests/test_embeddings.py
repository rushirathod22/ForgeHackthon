from __future__ import annotations

import math
import numpy as np
import pytest

from search.embeddings import VisualEmbeddingEngine


def test_embedding_engine_initialization():
    engine = VisualEmbeddingEngine(embedding_dim=128)
    assert engine.dim == 128


def test_image_embedding_unit_norm():
    engine = VisualEmbeddingEngine(embedding_dim=128)
    # Create synthetic RGB/BGR test image crop (e.g. 64x64 bright white region)
    white_img = np.ones((64, 64, 3), dtype=np.uint8) * 255
    vec = engine.embed_image(white_img)

    assert len(vec) == 128
    norm = math.sqrt(sum(x * x for x in vec))
    assert pytest.approx(norm, rel=1e-2) == 1.0


def test_text_embedding_unit_norm():
    engine = VisualEmbeddingEngine(embedding_dim=128)
    vec = engine.embed_text("white car entering main gate")

    assert len(vec) == 128
    norm = math.sqrt(sum(x * x for x in vec))
    assert pytest.approx(norm, rel=1e-2) == 1.0


def test_cosine_similarity_identity():
    engine = VisualEmbeddingEngine(embedding_dim=128)
    vec = [0.6, 0.8]
    assert pytest.approx(engine.cosine_similarity(vec, vec), rel=1e-3) == 1.0


def test_cosine_similarity_orthogonal():
    engine = VisualEmbeddingEngine(embedding_dim=128)
    vec1 = [1.0, 0.0]
    vec2 = [0.0, 1.0]
    assert pytest.approx(engine.cosine_similarity(vec1, vec2), abs=1e-4) == 0.0


def test_semantic_color_correlation():
    engine = VisualEmbeddingEngine(embedding_dim=128)
    # Bright white patch
    white_crop = np.ones((64, 64, 3), dtype=np.uint8) * 250
    # Red patch in BGR: (B=0, G=0, R=255)
    red_crop = np.zeros((64, 64, 3), dtype=np.uint8)
    red_crop[:, :, 2] = 255

    vec_white_crop = engine.embed_image(white_crop)
    vec_red_crop = engine.embed_image(red_crop)

    query_white = engine.embed_text("white vehicle")
    query_red = engine.embed_text("red vehicle")

    sim_white_to_white = engine.cosine_similarity(query_white, vec_white_crop)
    sim_white_to_red = engine.cosine_similarity(query_white, vec_red_crop)
    sim_red_to_red = engine.cosine_similarity(query_red, vec_red_crop)

    assert sim_white_to_white > sim_white_to_red
    assert sim_red_to_red > engine.cosine_similarity(query_red, vec_white_crop)


def test_empty_or_degenerate_inputs():
    engine = VisualEmbeddingEngine(embedding_dim=128)
    # Empty image
    empty_crop = np.zeros((0, 0, 3), dtype=np.uint8)
    vec = engine.embed_image(empty_crop)
    assert len(vec) == 128
    assert all(x == 0.0 for x in vec)

    # Empty text
    t_vec = engine.embed_text("")
    assert len(t_vec) == 128
    assert all(x == 0.0 for x in t_vec)
