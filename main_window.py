from PyQt5.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QHBoxLayout,
                             QWidget, QLabel, QLineEdit, QPushButton, QSpinBox,
                             QTableWidget, QTableWidgetItem, QHeaderView, QProgressBar,
                             QComboBox, QFileDialog, QMessageBox, QCompleter, QDialog)
from PyQt5.QtCore import QDate, Qt, QObject, pyqtSignal, QStringListModel
from PyQt5.QtGui import QFont, QValidator
from datetime import datetime
import sys
import csv
import re
from threading import Thread

from habr_parser import HabrParser
from ui_components import ClickableTableWidgetItem, DatePickerDialog


class DateValidator(QValidator):
    def validate(self, input_text, pos):
        # Проверка формата даты DD.MM.YYYY
        pattern = re.compile(r'^\d{0,2}[.]?\d{0,2}[.]?\d{0,4}$')
        if not pattern.fullmatch(input_text):
            return QValidator.Invalid, input_text, pos

        if len(input_text) == 10:
            try:
                datetime.strptime(input_text, "%d.%m.%Y")
                return QValidator.Acceptable, input_text, pos
            except ValueError:
                return QValidator.Invalid, input_text, pos

        return QValidator.Intermediate, input_text, pos


class HabrParserApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.parser = HabrParser()
        self.articles_data = []
        self.all_tags = set()
        self.is_parsing = False
        self.setWindowTitle("Habr Crawler")
        self.setGeometry(100, 100, 1600, 1080)
        self.init_ui()
        self.parser_thread = None

    def init_ui(self):
        # Установка основного шрифта
        font = QFont()
        font.setPointSize(12)
        self.setFont(font)

        main_widget = QWidget()
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)

        # Верхняя панель
        control_panel = QHBoxLayout()
        control_panel.setSpacing(15)

        # Блок дат
        date_panel = QHBoxLayout()
        date_panel.setSpacing(10)

        # Дата начала
        date_panel.addWidget(QLabel("Дата начала:"))
        self.start_date_edit = QLineEdit()
        self.start_date_edit.setPlaceholderText("дд.мм.гггг")
        self.start_date_edit.setFixedHeight(35)
        self.start_date_edit.setFixedWidth(120)
        self.start_date_edit.setValidator(DateValidator())
        start_date_btn = QPushButton("...")
        start_date_btn.setFixedSize(40, 35)
        start_date_btn.clicked.connect(lambda: self.show_date_picker(self.start_date_edit))
        date_panel.addWidget(self.start_date_edit)
        date_panel.addWidget(start_date_btn)

        # Дата окончания
        date_panel.addWidget(QLabel("Дата оконч.:"))
        self.end_date_edit = QLineEdit()
        self.end_date_edit.setPlaceholderText("дд.мм.гггг")
        self.end_date_edit.setFixedHeight(35)
        self.end_date_edit.setFixedWidth(120)
        self.end_date_edit.setValidator(DateValidator())
        end_date_btn = QPushButton("...")
        end_date_btn.setFixedSize(40, 35)
        end_date_btn.clicked.connect(lambda: self.show_date_picker(self.end_date_edit))
        date_panel.addWidget(self.end_date_edit)
        date_panel.addWidget(end_date_btn)

        # Добавляем блок дат в основную панель
        control_panel.addLayout(date_panel)

        # Блок настроек (макс. статей + кнопка + теги)
        settings_panel = QHBoxLayout()
        settings_panel.setSpacing(10)

        # Макс. статей
        settings_panel.addWidget(QLabel("Макс. статей:"))
        self.max_articles_spin = QSpinBox()
        self.max_articles_spin.setRange(0, 10000)
        self.max_articles_spin.setSpecialValueText("Все")
        self.max_articles_spin.setValue(0)
        self.max_articles_spin.setFixedHeight(35)
        self.max_articles_spin.setFixedWidth(100)
        settings_panel.addWidget(self.max_articles_spin)

        # Кнопка парсинга
        self.parse_btn = QPushButton("Начать парсинг")
        self.parse_btn.setFixedHeight(40)
        self.parse_btn.setMinimumWidth(150)
        settings_panel.addWidget(self.parse_btn)

        # Поле тегов с улучшенным автокомплитером
        settings_panel.addWidget(QLabel("Теги:"))
        self.tag_search = QComboBox()
        self.tag_search.setEditable(True)
        self.tag_search.setPlaceholderText("Доступно после парсинга")
        self.tag_search.setFixedHeight(35)
        self.tag_search.setEnabled(False)

        # Настраиваем автокомплитер
        self.tag_completer = QCompleter()
        self.tag_completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.tag_completer.setFilterMode(Qt.MatchContains)
        self.tag_completer.setCompletionMode(QCompleter.PopupCompletion)
        self.tag_search.setCompleter(self.tag_completer)

        # Подключаем сигнал для обновления подсказок при вводе
        self.tag_search.editTextChanged.connect(self.update_tag_completions)

        settings_panel.addWidget(self.tag_search, stretch=1)

        # Добавляем блок настроек в основную панель
        control_panel.addLayout(settings_panel)

        # Панель кнопок управления
        button_panel = QHBoxLayout()
        button_panel.setSpacing(10)

        self.export_btn = QPushButton("Экспорт в CSV")
        self.export_btn.setFixedHeight(40)
        self.export_btn.setMinimumWidth(150)

        self.reset_filter_btn = QPushButton("Сбросить фильтры")
        self.reset_filter_btn.setFixedHeight(40)
        self.reset_filter_btn.setMinimumWidth(150)

        self.stop_btn = QPushButton("Остановить")
        self.stop_btn.setFixedHeight(40)
        self.stop_btn.setMinimumWidth(150)
        self.stop_btn.setEnabled(False)

        self.sort_combo = QComboBox()
        self.sort_combo.addItems(["Сортировка", "Дата (старые)", "Дата (новые)", "Рейтинг", "Комментарии"])
        self.sort_combo.setFixedHeight(40)
        self.sort_combo.setMinimumWidth(200)

        button_panel.addWidget(self.export_btn)
        button_panel.addWidget(self.reset_filter_btn)
        button_panel.addWidget(self.stop_btn)
        button_panel.addWidget(self.sort_combo)

        # Прогресс-бар
        self.progress = QProgressBar()
        self.progress.setFixedHeight(25)
        self.progress.setVisible(False)

        # Таблица
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels(
            ["Дата", "Заголовок", "Ссылка", "Автор", "Рейтинг", "Комментарии", "Теги", "Краткое содержание"])

        header = self.table.horizontalHeader()
        for i in range(self.table.columnCount()):
            header.setSectionResizeMode(i, QHeaderView.Interactive)

        # Задаём стартовые ширины
        self.table.setColumnWidth(0, 90)
        self.table.setColumnWidth(1, 200)
        self.table.setColumnWidth(2, 200)
        self.table.setColumnWidth(3, 120)
        self.table.setColumnWidth(4, 80)
        self.table.setColumnWidth(5, 100)
        self.table.setColumnWidth(6, 150)
        self.table.setColumnWidth(7, 300)

        # Последний столбец будет растягиваться, если есть место
        self.table.horizontalHeader().setStretchLastSection(True)

        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.cellDoubleClicked.connect(self.cell_double_clicked)

        # Установка стилей
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f5f5;
            }
            QLabel {
                font-size: 14px;
            }
            QLineEdit, QComboBox, QSpinBox {
                font-size: 14px;
                padding: 5px;
                border: 1px solid #ccc;
                border-radius: 4px;
            }
            QPushButton {
                font-size: 14px;
                padding: 8px 16px;
                background-color: #4a90e2;
                color: white;
                border-radius: 4px;
                border: none;
            }
            QPushButton:hover {
                background-color: #3a7bc8;
            }
            QPushButton:disabled {
                background-color: #b0b0b0;
            }
            QTableWidget {
                font-size: 13px;
                alternate-background-color: #f9f9f9;
            }
            QHeaderView::section {
                font-size: 14px;
                padding: 8px;
                background-color: #e8e8e8;
                border: none;
            }
            QProgressBar {
                border: 1px solid #ccc;
                border-radius: 4px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #4CAF50;
            }
        """)

        # Сборка интерфейса
        main_layout.addLayout(control_panel)
        main_layout.addLayout(button_panel)
        main_layout.addWidget(self.progress)
        main_layout.addWidget(self.table)

        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)

        # Подключение сигналов
        self.parse_btn.clicked.connect(self.start_parsing)
        self.export_btn.clicked.connect(self.export_to_csv)
        self.reset_filter_btn.clicked.connect(self.reset_filters)
        self.stop_btn.clicked.connect(self.stop_parsing)
        self.sort_combo.currentIndexChanged.connect(self.sort_table)
        self.tag_search.currentTextChanged.connect(self.filter_by_tag)

        # Подключение сигналов парсера
        self.parser.parsing_finished.connect(self.on_parsing_finished)
        self.parser.progress_updated.connect(self.progress.setValue)
        self.parser.error_occurred.connect(self.show_error)

        self.export_btn.setEnabled(False)

        # Установка дат по умолчанию
        default_start = QDate.currentDate().addDays(-7)
        default_end = QDate.currentDate()
        self.start_date_edit.setText(default_start.toString("dd.MM.yyyy"))
        self.end_date_edit.setText(default_end.toString("dd.MM.yyyy"))

    def update_tag_completions(self, text):
        """Обновляет список подсказок для тегов по мере ввода"""
        if not text.strip():
            self.tag_completer.model().setStringList(sorted(self.all_tags))
        else:
            filtered_tags = [tag for tag in self.all_tags if text.lower() in tag.lower()]
            self.tag_completer.model().setStringList(sorted(filtered_tags))

    def show_date_picker(self, target_field):
        current_text = target_field.text()
        try:
            selected_date = QDate.fromString(current_text, "dd.MM.yyyy")
            if not selected_date.isValid():
                selected_date = QDate.currentDate()
        except:
            selected_date = QDate.currentDate()

        dialog = DatePickerDialog(self)
        dialog.calendar.setSelectedDate(selected_date)

        if dialog.exec_() == QDialog.Accepted:
            selected_date = dialog.selected_date()
            target_field.setText(selected_date.toString("dd.MM.yyyy"))

    def start_parsing(self):
        if self.is_parsing:
            return

        try:
            start_date = QDate.fromString(self.start_date_edit.text(), "dd.MM.yyyy").toString("yyyy-MM-dd")
            end_date = QDate.fromString(self.end_date_edit.text(), "dd.MM.yyyy").toString("yyyy-MM-dd")
            max_articles = self.max_articles_spin.value() if self.max_articles_spin.value() > 0 else None

            if not QDate.fromString(self.start_date_edit.text(), "dd.MM.yyyy").isValid() or \
                    not QDate.fromString(self.end_date_edit.text(), "dd.MM.yyyy").isValid():
                raise ValueError("Некорректный формат даты")

            self.is_parsing = True
            self.parse_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
            self.progress.setVisible(True)
            self.tag_search.setEnabled(False)

            self.table.setRowCount(0)
            self.parser.stop_parsing = False

            self.parser_thread = Thread(
                target=self.parser.parse_habr,
                args=(start_date, end_date, max_articles),
                daemon=True
            )
            self.parser_thread.start()

        except ValueError as e:
            QMessageBox.warning(self, "Ошибка", "Проверьте правильность введённых дат (дд.мм.гггг)")

    def stop_parsing(self):
        if self.is_parsing:
            self.parser.stop()
            if self.parser_thread and self.parser_thread.is_alive():
                self.parser_thread.join(timeout=1)
            self.is_parsing = False
            self.parse_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
            self.progress.setValue(0)

    def on_parsing_finished(self, articles_data, tags):
        self.is_parsing = False
        self.articles_data = articles_data
        self.all_tags = set()

        for tag_list in tags:
            self.all_tags.update(t.strip().lower() for t in tag_list.split(','))

        self.tag_completer_model = QStringListModel(sorted(self.all_tags))
        self.tag_completer.setModel(self.tag_completer_model)

        self.tag_search.setEnabled(True)
        self.tag_search.setPlaceholderText("Введите теги...")
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

    def show_error(self, message):
        QMessageBox.warning(self, "Ошибка", message)
        self.is_parsing = False
        self.parse_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
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
        elif index in (3, 4):  # Рейтинг или Комментарии
            col = 4 if index == 3 else 5
            rows = []

            # Собираем данные из видимых строк
            for row in range(self.table.rowCount()):
                if self.table.isRowHidden(row):
                    continue
                row_data = []
                for col_idx in range(self.table.columnCount()):
                    item = self.table.item(row, col_idx)
                    row_data.append(item.text() if item else "")
                try:
                    row_data[col] = int(row_data[col])
                except ValueError:
                    row_data[col] = 0
                rows.append(row_data)

            # Сортируем по числовому значению нужного столбца
            rows.sort(key=lambda x: x[col], reverse=True)

            # Обновляем таблицу отсортированными строками
            for i, row_data in enumerate(rows):
                for j, value in enumerate(row_data):
                    if isinstance(value, int):
                        value = str(value)
                    self.table.setItem(i, j, QTableWidgetItem(value))

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
                writer.writerow(
                    ["Дата", "Заголовок", "Ссылка", "Автор", "Рейтинг", "Комментарии", "Теги", "Краткое содержание"])
                for row in range(self.table.rowCount()):
                    row_data = [self.table.item(row, c).text() for c in range(8)]
                    writer.writerow(row_data)

            QMessageBox.information(self, "Успех", f"Данные сохранены в:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка экспорта:\n{str(e)}")

    def closeEvent(self, event):
        self.stop_parsing()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    window = HabrParserApp()
    window.show()
    sys.exit(app.exec_())
