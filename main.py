import requests
import sys
from lxml import html
from concurrent.futures import ThreadPoolExecutor, as_completed
from PyQt6.QtWidgets import QApplication, QTableWidgetItem, QHeaderView, QWidget
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtCore import QUrl, pyqtSignal
from tc2_2Form import Ui_TC_2_2_Form


class Form(QWidget, Ui_TC_2_2_Form):
    all_tasks_done_signal = pyqtSignal()  # сигнал означающий завершение парсинга всех ссылок

    def __init__(self):
        super().__init__()
        self.setupUi(self)  # составление формы
        self.js_enabled = False  # переключатель на работу с динамическим контентом
        self.urls = []  # список url
        self.xpath = ''  # XPath выражение

        self.rb_JsContent.toggled.connect(self.RB_update)
        self.te_forUrls.textChanged.connect(self.check_fields)
        self.te_forUrls.textChanged.connect(self.check_list)
        self.le_forXpath.textChanged.connect(self.check_fields)
        self.bt_Start.clicked.connect(self.start)
        self.bt_Clear.clicked.connect(self.clear_te)
        self.all_tasks_done_signal.connect(self.all_done)
        self.tw_results.setColumnWidth(0, 100)
        self.tw_results.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.tw_results.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)


    def RB_update(self):
        self.js_enabled = self.rb_JsContent.isChecked()

    def check_fields(self):
        if self.te_forUrls.toPlainText().strip() and self.le_forXpath.text().strip():
            self.bt_Start.setEnabled(True)
        else:
            self.bt_Start.setEnabled(False)

    def check_list(self):
        if self.te_forUrls.toPlainText().strip():
            self.bt_Clear.setEnabled(True)
        else:
            self.bt_Clear.setEnabled(False)

    def clear_te(self):
        self.te_forUrls.clear()

    def add_to_table(self, url, res):
        url = url[7:]
        row_position = self.tw_results.rowCount()
        self.tw_results.insertRow(row_position)
        self.tw_results.setItem(row_position, 0, QTableWidgetItem(str(url)))
        self.tw_results.setItem(row_position, 1, QTableWidgetItem(str(res)))
        self.tw_results.resizeRowsToContents()

    def all_done(self):
        for url, content in self.res.items():
            self.add_to_table(url, content)
        self.res.clear()

    def start(self):
        self.tw_results.setRowCount(0)
        self.bt_Start.setEnabled(False)
        text_urls = self.te_forUrls.toPlainText()
        self.urls = [line.strip() for line in text_urls.split(',') if line.strip()]
        self.xpath = self.le_forXpath.text()
        self.res = {}

        if self.js_enabled:  # если есть динамический JS контент, то он будет обрабатываться асинхронно
            self.opers = len(self.urls)
            for url in self.urls:
                self.scrape(url)
        else:  # если динамического JS контента нет, то ссылки обработаются параллельно в своих потоках
            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = {executor.submit(self.scrape, url): url for url in self.urls}
                for future in as_completed(futures):
                    url = futures[future]
                    content = future.result()
                    if content:
                        self.res[url] = content
            self.all_tasks_done_signal.emit()

    def scrape(self, url):
        if self.js_enabled:
            # Обработка динамического JS контента
            self.view = QWebEngineView()
            self.view.loadFinished.connect(lambda success: self.load_finished(success, url))
            self.view.load(QUrl(url))
        else:
            # Обработка статического контента
            content = fetch_parse_url(url, self.xpath)
            return content

    def load_finished(self, success, url):
        if success:
            self.view.page().toHtml(lambda html_content: self.handle_html(html_content, url))

    def handle_html(self, html_content, url):
        content = parse_html(html_content, self.xpath)
        self.res[url] = content
        self.view.loadFinished.disconnect()
        self.view.deleteLater()
        self.opers-=1
        if self.opers == 0:
            self.all_tasks_done_signal.emit()


def fetch_parse_url(url, xpath):  # работа со ссылкой
    response = send_get_request(url)
    if response:
        return parse_html(response.content, xpath)
    return None


def send_get_request(url):  # GET запрос через TCP
    try:
        response = requests.get(url)
        response.raise_for_status()  # Вызовет исключение, если запрос не успешен
        return response
    except requests.exceptions.HTTPError as http_err:  # Ошибка HTTP
        print(f'HTTP error occurred: {http_err}')
    except requests.exceptions.ConnectionError as conn_err:  # Ошибка соединения
        print(f'Connection error occurred: {conn_err}')
    except requests.exceptions.Timeout as timeout_err:  # Ошибка таймаута
        print(f'Timeout error occurred: {timeout_err}')
    except requests.exceptions.RequestException as err:  # Любая другая ошибка запроса
        print(f'An error occurred: {err}')
    return None


def parse_html(html_content, xpath):  # парсинг по полученному HTML с использованием XPath-выражения
    tree = html.fromstring(html_content)
    elements = tree.xpath(xpath)
    return [element.text_content().strip() for element in elements]


if __name__ == '__main__':
    app = QApplication(sys.argv)
    Window = Form()
    Window.show()
    sys.exit(app.exec())
