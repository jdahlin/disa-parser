"""Pytest fixtures for disa-parser tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from disa_parser import MockDocument, load_fixture


@pytest.fixture
def sample_fixture_data() -> dict:
    """Create a minimal fixture for testing."""
    return {
        "source": "test_exam.pdf",
        "page_count": 10,
        "pages": {
            "0": {
                "text_dict": {
                    "blocks": [
                        {
                            "type": 0,
                            "bbox": [50, 100, 500, 120],
                            "lines": [
                                {
                                    "bbox": [50, 100, 500, 120],
                                    "spans": [
                                        {
                                            "bbox": [50, 100, 150, 120],
                                            "text": "TENTAMEN",
                                            "font": "Arial",
                                            "color": 0,
                                        }
                                    ],
                                }
                            ],
                        },
                        {
                            "type": 0,
                            "bbox": [50, 200, 500, 220],
                            "lines": [
                                {
                                    "bbox": [50, 200, 500, 220],
                                    "spans": [
                                        {
                                            "bbox": [50, 200, 200, 220],
                                            "text": "Kurskod BIO123",
                                            "font": "Arial",
                                            "color": 0,
                                        },
                                    ],
                                }
                            ],
                        },
                    ]
                },
                "drawings": [],
            },
            "3": {
                "text_dict": {
                    "blocks": [
                        {
                            "type": 0,
                            "bbox": [30, 100, 60, 120],
                            "lines": [
                                {
                                    "bbox": [30, 100, 60, 120],
                                    "spans": [
                                        {
                                            "bbox": [30, 100, 50, 120],
                                            "text": "1",
                                            "font": "Arial",
                                            "color": 0,
                                        }
                                    ],
                                }
                            ],
                        },
                        {
                            "type": 0,
                            "bbox": [70, 100, 500, 140],
                            "lines": [
                                {
                                    "bbox": [70, 100, 500, 140],
                                    "spans": [
                                        {
                                            "bbox": [70, 100, 500, 140],
                                            "text": "What is the capital of Sweden?",
                                            "font": "Arial",
                                            "color": 0,
                                        }
                                    ],
                                }
                            ],
                        },
                        {
                            "type": 0,
                            "bbox": [70, 150, 300, 170],
                            "lines": [
                                {
                                    "bbox": [70, 150, 300, 170],
                                    "spans": [
                                        {
                                            "bbox": [70, 150, 300, 170],
                                            "text": "Stockholm",
                                            "font": "Georgia",
                                            "color": 0,
                                        }
                                    ],
                                }
                            ],
                        },
                        {
                            "type": 0,
                            "bbox": [70, 200, 200, 220],
                            "lines": [
                                {
                                    "bbox": [70, 200, 200, 220],
                                    "spans": [
                                        {
                                            "bbox": [70, 200, 200, 220],
                                            "text": "Totalpoäng: 1",
                                            "font": "Arial",
                                            "color": 0,
                                        }
                                    ],
                                }
                            ],
                        },
                    ]
                },
                "drawings": [],
            },
        },
    }


@pytest.fixture
def mcq_fixture_data() -> dict:
    """Create a fixture with multiple choice question."""
    return {
        "source": "mcq_exam.pdf",
        "page_count": 5,
        "pages": {
            "0": {
                "text_dict": {
                    "blocks": [
                        {
                            "type": 0,
                            "bbox": [50, 100, 500, 120],
                            "lines": [
                                {
                                    "bbox": [50, 100, 500, 120],
                                    "spans": [
                                        {
                                            "bbox": [50, 100, 150, 120],
                                            "text": "TENTAMEN",
                                            "font": "Arial",
                                            "color": 0,
                                        }
                                    ],
                                }
                            ],
                        },
                    ]
                },
                "drawings": [],
            },
            "1": {
                "text_dict": {
                    "blocks": [
                        {
                            "type": 0,
                            "bbox": [30, 100, 50, 120],
                            "lines": [
                                {
                                    "bbox": [30, 100, 50, 120],
                                    "spans": [
                                        {
                                            "bbox": [30, 100, 40, 120],
                                            "text": "1",
                                            "font": "Arial",
                                            "color": 0,
                                        }
                                    ],
                                }
                            ],
                        },
                        {
                            "type": 0,
                            "bbox": [30, 130, 50, 150],
                            "lines": [
                                {
                                    "bbox": [30, 130, 50, 150],
                                    "spans": [
                                        {
                                            "bbox": [30, 130, 40, 150],
                                            "text": "Flervalsfråga",
                                            "font": "Arial",
                                            "color": 0,
                                        }
                                    ],
                                }
                            ],
                        },
                    ]
                },
                "drawings": [],
            },
            "3": {
                "text_dict": {
                    "blocks": [
                        {
                            "type": 0,
                            "bbox": [30, 100, 60, 120],
                            "lines": [
                                {
                                    "bbox": [30, 100, 60, 120],
                                    "spans": [
                                        {
                                            "bbox": [30, 100, 50, 120],
                                            "text": "1",
                                            "font": "Arial",
                                            "color": 0,
                                        }
                                    ],
                                }
                            ],
                        },
                        {
                            "type": 0,
                            "bbox": [50, 100, 500, 120],
                            "lines": [
                                {
                                    "bbox": [50, 100, 500, 120],
                                    "spans": [
                                        {
                                            "bbox": [50, 100, 500, 120],
                                            "text": "Which element has atomic number 6?",
                                            "font": "Arial",
                                            "color": 0,
                                        }
                                    ],
                                }
                            ],
                        },
                        {
                            "type": 0,
                            "bbox": [70, 140, 300, 160],
                            "lines": [
                                {
                                    "bbox": [70, 140, 300, 160],
                                    "spans": [
                                        {
                                            "bbox": [70, 140, 300, 160],
                                            "text": "Oxygen",
                                            "font": "Arial",
                                            "color": 0,
                                        }
                                    ],
                                }
                            ],
                        },
                        {
                            "type": 0,
                            "bbox": [70, 170, 300, 190],
                            "lines": [
                                {
                                    "bbox": [70, 170, 300, 190],
                                    "spans": [
                                        {
                                            "bbox": [70, 170, 300, 190],
                                            "text": "Carbon",
                                            "font": "Arial",
                                            "color": 0,
                                        }
                                    ],
                                }
                            ],
                        },
                        {
                            "type": 0,
                            "bbox": [70, 200, 300, 220],
                            "lines": [
                                {
                                    "bbox": [70, 200, 300, 220],
                                    "spans": [
                                        {
                                            "bbox": [70, 200, 300, 220],
                                            "text": "Nitrogen",
                                            "font": "Arial",
                                            "color": 0,
                                        }
                                    ],
                                }
                            ],
                        },
                    ]
                },
                "drawings": [
                    # Green box marking Carbon as correct (at y=170)
                    {
                        "rect": [65, 168, 75, 192],
                        "fill": (0.1, 0.6, 0.1),  # Green
                        "color": None,
                    }
                ],
            },
        },
    }


@pytest.fixture
def mock_document(sample_fixture_data: dict) -> MockDocument:
    """Create a MockDocument from sample fixture data."""
    return load_fixture(sample_fixture_data)


@pytest.fixture
def mcq_document(mcq_fixture_data: dict) -> MockDocument:
    """Create a MockDocument with MCQ from fixture data."""
    return load_fixture(mcq_fixture_data)
