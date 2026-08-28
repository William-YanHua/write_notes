import importlib.util
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).parents[1] / "scripts" / "knowledge_store.py"
SPEC = importlib.util.spec_from_file_location("knowledge_store", SCRIPT_PATH)
assert SPEC and SPEC.loader
knowledge_store = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(knowledge_store)


class DocumentReuseTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.project_root = Path(self.temporary_directory.name).resolve()
        self.knowledge_dir = knowledge_store.initialize(self.project_root, None)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    @staticmethod
    def document(document_id: str, **overrides: object) -> dict[str, object]:
        paragraph = (
            "项目文档需要长期保持单一入口，并在新信息出现时重新组织相关章节。"
            "这样可以避免相同事实散落在多个文件中，也能让读者从项目整体理解背景、方案和边界。"
        ) * 5
        value: dict[str, object] = {
            "action": "add",
            "semantic_rewrite": True,
            "id": document_id,
            "title": "项目主文档",
            "type": "project-guide",
            "status": "stable",
            "summary": "说明项目的整体知识。",
            "audience": ["项目维护者"],
            "scope": "整个项目",
            "source_log_ids": [],
            "sources": ["用户确认"],
            "body": (
                f"## 背景与目标\n\n{paragraph}\n\n"
                f"## 方案与维护\n\n{paragraph}\n\n"
                f"## 边界与验证\n\n{paragraph}"
            ),
            "updated_at": "2026-08-24",
        }
        value.update(overrides)
        return value

    def write_document(self, value: dict[str, object]) -> str:
        return knowledge_store.add_or_update_document(
            self.knowledge_dir, knowledge_store.validate_document(value)
        )

    def test_second_document_requires_explicit_split(self) -> None:
        self.assertEqual(self.write_document(self.document("project-guide")), "added")

        with self.assertRaisesRegex(
            knowledge_store.KnowledgeError, "already has a document"
        ):
            self.write_document(self.document("feature-guide"))

    def test_split_document_requires_existing_source_and_reason(self) -> None:
        self.write_document(self.document("project-guide"))

        with self.assertRaisesRegex(
            knowledge_store.KnowledgeError, "split source document does not exist"
        ):
            self.write_document(
                self.document(
                    "operations-guide",
                    split_from="missing-guide",
                    split_reason="由独立团队长期维护并单独发布。",
                )
            )

        self.assertEqual(
            self.write_document(
                self.document(
                    "operations-guide",
                    split_from="project-guide",
                    split_reason="由独立团队长期维护并单独发布。",
                )
            ),
            "added",
        )

    def test_split_origin_is_preserved_on_update(self) -> None:
        self.write_document(self.document("project-guide"))
        self.write_document(
            self.document(
                "operations-guide",
                split_from="project-guide",
                split_reason="由独立团队长期维护并单独发布。",
            )
        )

        updated = self.document(
            "operations-guide",
            action="update",
            title="运维指南",
        )
        self.assertEqual(self.write_document(updated), "updated")

        metadata = knowledge_store.extract_document_metadata(
            (self.knowledge_dir / "documents" / "operations-guide.md").read_text(
                encoding="utf-8"
            )
        )
        self.assertIsNotNone(metadata)
        self.assertEqual(metadata["split_from"], "project-guide")
        self.assertEqual(metadata["split_reason"], "由独立团队长期维护并单独发布。")

    def test_split_document_cannot_become_another_split_source(self) -> None:
        self.write_document(self.document("project-guide"))
        self.write_document(
            self.document(
                "operations-guide",
                split_from="project-guide",
                split_reason="由独立团队长期维护并单独发布。",
            )
        )

        with self.assertRaisesRegex(
            knowledge_store.KnowledgeError, "directly from the primary document"
        ):
            self.write_document(
                self.document(
                    "on-call-guide",
                    split_from="operations-guide",
                    split_reason="由值班团队单独维护。",
                )
            )

    def test_document_style_defaults_from_document_type(self) -> None:
        value = knowledge_store.validate_document(self.document("project-guide"))

        self.assertEqual(value["writing_style"], "explanatory")
        self.assertIsNone(value["style_notes"])

    def test_explicit_document_style_is_saved_in_metadata(self) -> None:
        self.write_document(
            self.document(
                "project-guide",
                writing_style="technical",
                style_notes="面向数据开发，说明处理规则并提供输入输出示例。",
            )
        )

        metadata = knowledge_store.extract_document_metadata(
            (self.knowledge_dir / "documents" / "project-guide.md").read_text(
                encoding="utf-8"
            )
        )
        self.assertIsNotNone(metadata)
        self.assertEqual(metadata["writing_style"], "technical")
        self.assertEqual(
            metadata["style_notes"],
            "面向数据开发，说明处理规则并提供输入输出示例。",
        )

    def test_custom_style_requires_notes(self) -> None:
        with self.assertRaisesRegex(
            knowledge_store.KnowledgeError, "custom writing style requires style_notes"
        ):
            knowledge_store.validate_document(
                self.document("project-guide", writing_style="custom")
            )

    def test_document_rejects_review_traces_and_generic_headings(self) -> None:
        paragraph = (
            "数据清洗按字段类型分别执行标准化、缺失值处理和异常值识别。"
            "每项规则都说明输入条件、转换过程和输出结果，便于开发者理解和实现。"
        ) * 5
        for fragment in (
            "## 影响与验收\n\n" + paragraph,
            "## 字段处理\n\n根据用户建议修改这一部分。" + paragraph,
        ):
            body = (
                f"## 数据来源\n\n{paragraph}\n\n"
                f"## 清洗方法\n\n{paragraph}\n\n{fragment}"
            )
            with self.subTest(fragment=fragment[:30]):
                with self.assertRaises(knowledge_store.KnowledgeError):
                    knowledge_store.validate_document(
                        self.document("project-guide", body=body)
                    )


if __name__ == "__main__":
    unittest.main()
