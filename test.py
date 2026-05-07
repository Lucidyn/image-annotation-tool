import sys
import json
from pathlib import Path
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("图片文字标注工具")
        self.resize(900, 650)
        self.image_paths = []
        self.current_index = -1
        self.annotations = {}
        self.label_file = None
        self.folder = None
        self._setup_ui()
        self._setup_shortcuts()

    def _setup_ui(self):
        tb = self.addToolBar("工具")
        tb.setMovable(False)
        tb.addAction("📂 打开文件夹", self.open_folder)
        tb.addSeparator()
        tb.addAction("◀ 上一张", self.go_prev)
        tb.addAction("▶ 下一张", self.go_next)
        tb.addSeparator()
        self.progress_label = QLabel("  未打开文件夹")
        tb.addWidget(self.progress_label)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # 左侧图片列表
        self.img_list = QListWidget()
        self.img_list.setIconSize(QSize(72, 72))
        self.img_list.setFixedWidth(190)
        self.img_list.currentRowChanged.connect(self._on_list_select)
        splitter.addWidget(self.img_list)

        # 右侧
        right = QWidget()
        vbox = QVBoxLayout(right)
        vbox.setContentsMargins(8, 8, 8, 8)
        vbox.setSpacing(8)

        self.img_label = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self.img_label.setStyleSheet("background:#1a1a1a; border-radius:6px;")
        self.img_label.setMinimumHeight(380)
        vbox.addWidget(self.img_label, stretch=1)

        ann_group = QGroupBox("文字内容标注")
        ann_layout = QVBoxLayout(ann_group)

        hint = QLabel("输入图片中的文字内容，完成后按 Ctrl+S 保存并跳转下一张，方向键左右切换图片。")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: gray; font-size: 12px;")
        ann_layout.addWidget(hint)

        self.text_edit = QPlainTextEdit()
        self.text_edit.setPlaceholderText("请输入图片中的文字内容...")
        self.text_edit.setFixedHeight(80)
        ann_layout.addWidget(self.text_edit)

        btn_row = QHBoxLayout()
        btn_save = QPushButton("✅ 保存并下一张  (Ctrl+S)")
        btn_save.clicked.connect(self.save_and_next)
        btn_row.addWidget(btn_save)
        btn_row.addStretch()
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #1D9E75; font-size: 12px;")
        btn_row.addWidget(self.status_label)
        ann_layout.addLayout(btn_row)

        vbox.addWidget(ann_group)
        splitter.addWidget(right)
        splitter.setSizes([190, 710])
        self.setCentralWidget(splitter)

    def _setup_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+S"), self, self.save_and_next)
        QShortcut(QKeySequence("Left"),   self, self.go_prev)
        QShortcut(QKeySequence("Right"),  self, self.go_next)

    def open_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "选择图片文件夹")
        if not folder:
            return
        self.folder = Path(folder)
        self.label_file = self.folder / "label.txt"

        # 读取已有标注
        self.annotations = {}
        if self.label_file.exists():
            with open(self.label_file, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if "\t" not in line:
                        continue
                    img_name, text = line.split("\t", 1)
                    self.annotations[img_name] = text

        # 扫描图片
        exts = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tiff"}
        self.image_paths = sorted(
            p for p in self.folder.iterdir() if p.suffix.lower() in exts
        )

        self._refresh_list()
        if self.image_paths:
            self.img_list.setCurrentRow(0)

    def _refresh_list(self):
        self.img_list.clear()
        for p in self.image_paths:
            icon = QIcon(str(p))
            item = QListWidgetItem(icon, p.name)
            item.setData(Qt.ItemDataRole.UserRole, p)
            if self.annotations.get(p.name, "").strip():
                item.setForeground(QColor("#1D9E75"))
            self.img_list.addItem(item)
        self._update_progress()

    def _update_progress(self):
        total = len(self.image_paths)
        done = sum(1 for p in self.image_paths if self.annotations.get(p.name, "").strip())
        self.progress_label.setText(f"  进度：{done} / {total}")

    def _on_list_select(self, row):
        if row < 0 or row >= len(self.image_paths):
            return
        self.current_index = row
        path = self.image_paths[row]

        pixmap = QPixmap(str(path))
        scaled = pixmap.scaled(
            self.img_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.img_label.setPixmap(scaled)
        self.text_edit.setPlainText(self.annotations.get(path.name, ""))
        self.text_edit.setFocus()
        self.status_label.setText("")

    def go_prev(self):
        if self.current_index > 0:
            self.img_list.setCurrentRow(self.current_index - 1)

    def go_next(self):
        if self.current_index < len(self.image_paths) - 1:
            self.img_list.setCurrentRow(self.current_index + 1)

    def save_current(self):
        if self.current_index < 0 or not self.label_file:
            return
        path = self.image_paths[self.current_index]
        text = self.text_edit.toPlainText().strip()

        # 更新内存
        self.annotations[path.name] = text

        # 更新列表颜色
        item = self.img_list.item(self.current_index)
        item.setForeground(QColor("#1D9E75") if text else QColor("#888888"))

        self._update_progress()
        self._write_label_file()
        self.status_label.setText("✅ 已保存")

    def save_and_next(self):
        self.save_current()
        self.go_next()

    def _write_label_file(self):
        """实时将全部标注写入 label.txt，格式：图片名\t文字内容"""
        with open(self.label_file, "w", encoding="utf-8") as f:
            for p in self.image_paths:
                text = self.annotations.get(p.name, "").strip()
                if text:
                    f.write(f"{p.name}\t{text}\n")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())