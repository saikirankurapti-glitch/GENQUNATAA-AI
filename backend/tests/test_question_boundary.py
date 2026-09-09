from app.question_boundary import QuestionBoundaryDetector


def test_question_boundary_waits_for_complete_turn() -> None:
    detector = QuestionBoundaryDetector()
    detector.add("Can you explain")
    assert detector.flush() is not None


def test_question_boundary_extracts_explicit_question() -> None:
    detector = QuestionBoundaryDetector()
    detector.add("Tell me about your Azure Databricks project?")
    boundary = detector.flush()
    assert boundary is not None
    assert boundary.text.endswith("?")
    assert boundary.confidence == 0.98


def test_question_boundary_ignores_normal_commentary() -> None:
    detector = QuestionBoundaryDetector()
    detector.add("Thanks for joining today. Let's start with the project.")
    assert detector.flush() is None


def test_question_boundary_deduplicates() -> None:
    detector = QuestionBoundaryDetector()
    detector.add("Why did you use Databricks?")
    first = detector.flush()
    detector.add("Why did you use Databricks?")
    second = detector.flush()
    assert first is not None
    assert second is None
