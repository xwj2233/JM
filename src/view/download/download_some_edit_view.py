import os

from PySide6.QtCore import Signal
from PySide6.QtGui import Qt
from PySide6.QtWidgets import QFileDialog, QHeaderView, QAbstractItemView

from component.dialog.base_mask_dialog import BaseMaskDialog
from component.label.gif_label import GifLabel
from config import config
from config.setting import Setting
from interface.ui_download_dir import Ui_DownloadDir
from interface.ui_download_some_edit import Ui_DownloadSomeEdit
from qt_owner import QtOwner
from task.qt_task import QtTaskBase
from task.task_upload import QtUpTask
from tools.str import Str
import re

class DownloadSomeEditView(BaseMaskDialog, Ui_DownloadSomeEdit, QtTaskBase):
    SaveLogin = Signal(list)
    MAX_INPUT_COUNT = 1000

    def __init__(self, parent=None, nextID=1):
        BaseMaskDialog.__init__(self, parent)
        Ui_DownloadSomeEdit.__init__(self)
        QtTaskBase.__init__(self)
        self.widget.adjustSize()
        self.setupUi(self.widget)
        self.closeButton.clicked.connect(self.close)
        self.saveButton.clicked.connect(self.Save)
        self.label.setText("请输入JM号，支持 jm123456、123456、100000-100010")

    def ParseBookIds(self, data):
        bookIds = []
        seen = set()

        def addBookId(bookId):
            if bookId in seen:
                return
            seen.add(bookId)
            bookIds.append(bookId)

        normalized = data.lower()
        for startText, endText in re.findall(r'(?:jm)?(\d+)\s*[-~～—–]\s*(?:jm)?(\d+)', normalized):
            start = int(startText)
            end = int(endText)
            step = 1 if start <= end else -1
            for bookId in range(start, end + step, step):
                addBookId(bookId)
                if len(bookIds) >= self.MAX_INPUT_COUNT:
                    return bookIds

        normalized = re.sub(r'(?:jm)?\d+\s*[-~～—–]\s*(?:jm)?\d+', ' ', normalized)
        for bookIdText in re.findall(r'(?:jm)?(\d+)', normalized):
            addBookId(int(bookIdText))
            if len(bookIds) >= self.MAX_INPUT_COUNT:
                break

        return bookIds
        
    def Save(self):
        data = self.textEdit.toPlainText()
        allBookIds = self.ParseBookIds(data)
        if not allBookIds:
            QtOwner().ShowError(Str.GetStr(Str.NotSpace))
            return
        self.SaveLogin.emit(allBookIds)
        self.close()
        return
    
