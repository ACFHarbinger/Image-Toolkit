import sys
from pathlib import Path

from PIL import Image
from PySide6.QtWidgets import QApplication

from gui.src.components.dialogs.contact_sheet_dialog import ContactSheetDialog
from gui.src.utils.contact_sheet_generator import generate_contact_sheet

if not QApplication.instance():
    app = QApplication(sys.argv)


def _create_dummy_image(path: Path, color: tuple[int, int, int] = (255, 0, 0)) -> str:
    img = Image.new("RGB", (100, 100), color)
    img.save(str(path))
    return str(path)


def test_contact_sheet_generator(tmp_path: Path):
    # Create 5 test images
    img_paths = [
        _create_dummy_image(tmp_path / f"img_{i}.png", color=(i * 40, 100, 150))
        for i in range(5)
    ]

    out_file = tmp_path / "sheet_out.png"

    # Generate 3-column contact sheet
    sheet = generate_contact_sheet(
        image_paths=img_paths,
        columns=3,
        thumb_size=(100, 100),
        padding=10,
        margin=20,
        show_labels=True,
        output_path=str(out_file),
    )

    assert out_file.exists()
    assert sheet.width == 2 * 20 + 3 * 100 + 2 * 10  # 40 + 300 + 20 = 360
    # 5 images in 3 columns = 2 rows
    cell_h = 100 + 24  # 124
    assert sheet.height == 2 * 20 + 2 * cell_h + 1 * 10  # 40 + 248 + 10 = 298


def test_contact_sheet_dialog_ui(tmp_path: Path):
    img_paths = [
        _create_dummy_image(tmp_path / f"img_{i}.png")
        for i in range(3)
    ]

    dlg = ContactSheetDialog(image_paths=img_paths)
    assert dlg.spin_columns.value() == 3
    assert dlg.chk_labels.isChecked()
    assert dlg._get_thumb_size() == (256, 256)

    # Change combo to Small
    dlg.combo_size.setCurrentIndex(0)
    assert dlg._get_thumb_size() == (128, 128)
