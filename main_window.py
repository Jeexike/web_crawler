from PyQt5.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, 
                            QWidget, QLabel, QLineEdit, QPushButton, QSpinBox,
                            QTableWidget, QTableWidgetItem, QHeaderView, QProgressBar,
                            QComboBox, QFileDialog, QMessageBox, QCompleter, QDialog)
from PyQt5.QtCore import QDate, Qt, QObject, pyqtSignal
from PyQt5.QtGui import QFont
from datetime import datetime
import sys
import csv
import os
from threading import Thread

from habr_parser import HabrParser
from ui_components import ClickableTableWidgetItem, DatePickerDialog


class HabrParserApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.parser = HabrParser()
        self.articles_data = []
        self.all_tags = set()
        self.setWindowTitle("Habr Crawler")
        self.setGeometry(100, 100, 1920, 1080)
        self.init_ui()
        self.parser_thread = None

    def init_ui(self):
        main_widget = QWidget()
        main_layout = QVBoxLayout()



        control_panel = QHBoxLayout()

        date_panel = QHBoxLayout()
        
        self.start_date_edit = QLineEdit()
        self.start_date_edit.setReadOnly(True)
        self.start_date_edit.setPlaceholderText("Дата начала")
        start_date_btn = QPushButton("...")
        start_date_btn.setFixedWidth(30)
        start_date_btn.clicked.connect(lambda: self.show_date_picker(self.start_date_edit))
        
        self.end_date_edit = QLineEdit()
        self.end_date_edit.setReadOnly(True)
        self.end_date_edit.setPlaceholderText("Дата окончания")
        end_date_btn = QPushButton("...")
        end_date_btn.setFixedWidth(30)
        end_date_btn.clicked.connect(lambda: self.show_date_picker(self.end_date_edit))
        
        default_start = QDate.currentDate().addDays(-7)
        default_end = QDate.currentDate()
        self.start_date_edit.setText(default_start.toString("dd.MM.yyyy"))
        self.end_date_edit.setText(default_end.toString("dd.MM.yyyy"))
        
        date_panel.addWidget(QLabel("Дата начала:"))
        date_panel.addWidget(self.start_date_edit)
        date_panel.addWidget(start_date_btn)
        date_panel.addWidget(QLabel("Дата окончания:"))
        date_panel.addWidget(self.end_date_edit)
        date_panel.addWidget(end_date_btn)

        settings_panel = QHBoxLayout()
        self.max_articles_spin = QSpinBox()
        self.max_articles_spin.setRange(0, 10000)
        self.max_articles_spin.setSpecialValueText("Все")
        self.max_articles_spin.setValue(0)
        
        self.tag_search = QComboBox()
        self.tag_search.setEditable(True)
        self.tag_search.setPlaceholderText("Фильтр по тегам...")
        
        completer = QCompleter()
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.tag_search.setCompleter(completer)
        
        settings_panel.addWidget(QLabel("Макс. статей:"))
        settings_panel.addWidget(self.max_articles_spin)
        settings_panel.addWidget(QLabel("Теги:"))
        settings_panel.addWidget(self.tag_search, stretch=1)

        button_panel = QHBoxLayout()
        self.parse_btn = QPushButton("Начать парсинг")
        self.export_btn = QPushButton("Экспорт в CSV")
        self.reset_filter_btn = QPushButton("Сбросить фильтры")
        self.stop_btn = QPushButton("Остановить")
        self.stop_btn.setEnabled(False)
        self.sort_combo = QComboBox()
        self.sort_combo.addItems(["Сортировка", "Дата (новые)", "Дата (старые)", "Рейтинг", "Комментарии"])
        
        button_panel.addWidget(self.parse_btn)
        button_panel.addWidget(self.export_btn)
        button_panel.addWidget(self.reset_filter_btn)
        button_panel.addWidget(self.stop_btn)
        button_panel.addWidget(self.sort_combo)

        self.progress = QProgressBar()
        self.progress.setVisible(False)

        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels(["Дата", "Заголовок", "Ссылка", "Автор", "Рейтинг", "Комментарии", "Теги", "Краткое содержание"])
        
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.setColumnWidth(0, 100)
        self.table.setColumnWidth(2, 200)
        self.table.setColumnWidth(3, 150)
        self.table.setColumnWidth(6, 200)
        self.table.setColumnWidth(7, 300)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.cellDoubleClicked.connect(self.cell_double_clicked)

        control_panel.addLayout(date_panel)
        control_panel.addLayout(settings_panel)
        main_layout.addLayout(control_panel)
        main_layout.addLayout(button_panel)
        main_layout.addWidget(self.progress)
        main_layout.addWidget(self.table)

        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)

        self.parse_btn.clicked.connect(self.start_parsing)
        self.export_btn.clicked.connect(self.export_to_csv)
        self.reset_filter_btn.clicked.connect(self.reset_filters)
        self.stop_btn.clicked.connect(self.stop_parsing)
        self.sort_combo.currentIndexChanged.connect(self.sort_table)
        self.tag_search.currentTextChanged.connect(self.filter_by_tag)

        self.export_btn.setEnabled(False)

    def show_date_picker(self, target_field):
        dialog = DatePickerDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            selected_date = dialog.selected_date()
            target_field.setText(selected_date.toString("dd.MM.yyyy"))

    def start_parsing(self):
        self.parse_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.progress.setVisible(True)
        self.progress.setValue(0)
        
        try:
            start_date = QDate.fromString(self.start_date_edit.text(), "dd.MM.yyyy").toString("yyyy-MM-dd")
            end_date = QDate.fromString(self.end_date_edit.text(), "dd.MM.yyyy").toString("yyyy-MM-dd")
            max_articles = self.max_articles_spin.value() if self.max_articles_spin.value() > 0 else None
        except ValueError:
            QMessageBox.warning(self, "Ошибка", "Проверьте правильность введенных данных")
            self.progress.setVisible(False)
            self.parse_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
            return

        self.table.setRowCount(0)
        self.parser.stop_parsing = False
        
        self.parser.parsing_finished.connect(self.on_parsing_finished)
        self.parser.progress_updated.connect(self.progress.setValue)
        self.parser.error_occurred.connect(lambda msg: QMessageBox.warning(self, "Ошибка", msg))
        
        self.parser_thread = Thread(
            target=self.parser.parse_habr,
            args=(start_date, end_date, max_articles),
            daemon=True
        )
        self.parser_thread.start()

    def on_parsing_finished(self, articles_data, tags):
        self.articles_data = articles_data
        self.all_tags = set()
        for tag_list in tags:
            self.all_tags.update(t.strip() for t in tag_list.split(','))
        
        self.tag_search.clear()
        self.tag_search.addItem("")
        self.tag_search.addItems(sorted(self.all_tags))

        for article in self.articles_data:
            row = self.table.rowCount()
            self.table.insertRow(row)

            formatted_date = datetime.strptime(article[0], "%Y-%m-%d").strftime("%d.%m.%Y")
            self.table.setItem(row, 0, QTableWidgetItem(formatted_date))
            
            title_item = QTableWidgetItem(article[1])
            title_item.setToolTip(article[1])
            self.table.setItem(row, 1, title_item)
            
            self.table.setItem(row, 2, ClickableTableWidgetItem(article[2], article[2]))
            
            self.table.setItem(row, 3, QTableWidgetItem(article[3]))
            
            rating = QTableWidgetItem(article[4])
            rating.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 4, rating)
            
            comments = QTableWidgetItem(article[5])
            comments.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 5, comments)
            
            cleaned_tags = ', '.join(t.strip() for t in article[6].split(','))
            tag_item = QTableWidgetItem(cleaned_tags)
            tag_item.setToolTip(cleaned_tags)
            self.table.setItem(row, 6, tag_item)
            
            full_desc = article[7]
            short_desc = (full_desc[:150] + '...') if len(full_desc) > 150 else full_desc
            desc_item = QTableWidgetItem(short_desc)
            desc_item.setToolTip(full_desc)
            desc_item.setData(Qt.UserRole, full_desc)
            self.table.setItem(row, 7, desc_item)

        self.progress.setValue(100)
        self.parse_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.export_btn.setEnabled(True)
        self.parser_thread = None

    def stop_parsing(self):
        self.parser.stop()
        if self.parser_thread and self.parser_thread.is_alive():
            self.parser_thread.join(timeout=1)
        self.stop_btn.setEnabled(False)
        self.parse_btn.setEnabled(True)
        self.progress.setValue(0)

    def cell_double_clicked(self, row, col):
        if col == 2:
            item = self.table.item(row, col)
            if isinstance(item, ClickableTableWidgetItem):
                item.open_link()
        elif col == 7:
            item = self.table.item(row, col)
            if item:
                full_text = item.data(Qt.UserRole)
                if full_text:
                    QMessageBox.information(self, "Краткое содержание статьи", full_text)

    def filter_by_tag(self, tag):
        tag = tag.strip().lower()
        for row in range(self.table.rowCount()):
            tags_item = self.table.item(row, 6)
            if not tag:
                self.table.setRowHidden(row, False)
            elif tags_item:
                article_tags = [t.strip().lower() for t in tags_item.text().split(',')]
                self.table.setRowHidden(row, tag not in article_tags)
            else:
                self.table.setRowHidden(row, True)

    def reset_filters(self):
        self.tag_search.setCurrentIndex(0)
        self.sort_combo.setCurrentIndex(0)
        for row in range(self.table.rowCount()):
            self.table.setRowHidden(row, False)

    def sort_table(self, index):
        if not self.articles_data:
            return
            
        if index == 1:
            self.table.sortItems(0, Qt.DescendingOrder)
        elif index == 2:
            self.table.sortItems(0, Qt.AscendingOrder)
        elif index == 3:
            self.table.sortItems(4, Qt.DescendingOrder)
        elif index == 4:
            self.table.sortItems(5, Qt.DescendingOrder)

    def export_to_csv(self):
        if not self.articles_data:
            QMessageBox.warning(self, "Ошибка", "Нет данных для экспорта")
            return

        path, _ = QFileDialog.getSaveFileName(
            self, 
            "Сохранить CSV", 
            "", 
            "CSV (*.csv)"
        )
        
        if not path:
            return
            
        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f, delimiter=';')
                writer.writerow(["Дата", "Заголовок", "Ссылка", "Автор", "Рейтинг", "Комментарии", "Теги", "Краткое содержание"])
                for row in range(self.table.rowCount()):
                    row_data = [self.table.item(row, c).text() for c in range(8)]
                    writer.writerow(row_data)
            
            QMessageBox.information(self, "Успех", f"Данные сохранены в:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка экспорта:\n{str(e)}")

    def closeEvent(self, event):
        self.stop_parsing()
        event.accept()