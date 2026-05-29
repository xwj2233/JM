from config import config
from config.setting import Setting
from task.qt_task import QtTaskBase
from tools.log import Log
from tools.status import Status
from tools.str import Str
from tools.tool import ToolUtil
from view.download.download_db import DownloadDb
from view.download.download_item import DownloadItem


class DownloadStatus(QtTaskBase):
    def __init__(self):
        QtTaskBase.__init__(self)
        self.db = DownloadDb()
        self.downloadingList = []  # 正在下载列表
        self.downloadList = []  # 下载队列
        self.downloadDict = {}  # bookId ：downloadInfo
        self.convertList = []
        self.convertingList = []
        self.downloadNotifyActive = False
        self.downloadNotifyPending = set()
        self.downloadNotifySuccess = set()
        self.downloadNotifyFail = set()

    def SetNewStatus(self, task, status, statusMsg=""):
        if status == task.status:
            return
        task.status = status
        task.statusMsg = statusMsg
        task.dirty = True
        assert isinstance(task, DownloadItem)
        if status == task.Waiting:
            self._SetTaskWait(task)
        elif status == task.Pause:
            self._SetTaskPause(task)
        elif status == task.Error:
            self._SetDownloadTaskNone(task)
            Log.Warn("Download error, bookId:{}, epsId:{}, index:{}, stMsg:{}".format(task.bookId, task.curDownloadEpsId, task.curDownloadPic, task.statusMsg))
        elif status == task.Downloading:
            self._SetTaskDownloading(task)
        elif status == task.Success:
            self._SetDownloadTaskNone(task)
        else:
            assert False
        self.UpdateTableItem(task)
        self._UpdateDownloadNotify(task, status)

    def SetNewCovertStatus(self, task, status, msg=""):
        assert isinstance(task, DownloadItem)
        if task.convertStatus == status:
            return
        task.convertStatus = status
        task.convertMsg = msg
        if status == task.Waiting:
            self._SetTaskConvertWait(task)
        elif status == task.Pause:
            self._SetTaskConvertPause(task)
        elif status == task.Error:
            self._SetTaskConvertNone(task)
            Log.Warn("Convert error, bookId:{}, epsId:{}, index:{}, stMsg:{}".format(task.bookId, task.curConvertEpsId, task.curConvertCnt, task.convertMsg))
        elif status == task.Converting:
            self._SetTaskConverting(task)
        elif status == task.ConvertSuccess:
            self._SetTaskConvertNone(task)
        else:
            assert False
        self.UpdateTableItem(task)

    def _SetTaskWait(self, task):
        if task in self.downloadingList:
            self.downloadingList.remove(task)
        if task not in self.downloadList:
            self.downloadList.append(task)
        return

    def _SetTaskConvertWait(self, task):
        task.convertStatus = task.Waiting
        if task in self.convertingList:
            self.convertingList.remove(task)
        if task not in self.convertList:
            self.convertList.append(task)
        return

    def _SetTaskDownloading(self, task):
        if task not in self.downloadingList:
            self.downloadingList.append(task)
        if task in self.downloadList:
            self.downloadList.remove(task)
        return

    def _SetTaskConverting(self, task):
        if task not in self.convertingList:
            self.convertingList.append(task)
        if task in self.convertList:
            self.convertList.remove(task)
        return

    def _SetTaskPause(self, task2):
        from task.task_download import TaskDownload
        TaskDownload().Cancel(task2.cleanFlag)
        self._SetDownloadTaskNone(task2)
        return

    def _SetTaskConvertPause(self, task2):
        task2.convertStatus = task2.Pause
        from task.task_waifu2x import TaskWaifu2x
        TaskWaifu2x().Cancel(task2.cleanFlag)
        self._SetTaskConvertNone(task2)
        return

    def _SetDownloadTaskNone(self, task):
        if task in self.downloadingList:
            self.downloadingList.remove(task)
        if task in self.downloadList:
            self.downloadList.remove(task)
        return

    def _SetTaskConvertNone(self, task):
        if task in self.convertingList:
            self.convertingList.remove(task)
        if task in self.convertList:
            self.convertList.remove(task)
        return

    def _UpdateDownloadNotify(self, task, status):
        bookId = str(task.bookId)
        if status in [task.Waiting, task.Downloading]:
            if not self.downloadNotifyActive:
                self.downloadNotifyActive = True
                self.downloadNotifyPending.clear()
                self.downloadNotifySuccess.clear()
                self.downloadNotifyFail.clear()
            self.downloadNotifyPending.add(bookId)
            self.downloadNotifySuccess.discard(bookId)
            self.downloadNotifyFail.discard(bookId)
            return

        if not self.downloadNotifyActive:
            return

        if status == task.Success:
            self.downloadNotifyPending.discard(bookId)
            self.downloadNotifySuccess.add(bookId)
            self.downloadNotifyFail.discard(bookId)
        elif status == task.Error:
            self.downloadNotifyPending.discard(bookId)
            self.downloadNotifyFail.add(bookId)
            self.downloadNotifySuccess.discard(bookId)
        elif status == task.Pause:
            self.downloadNotifyPending.discard(bookId)

        self._ShowDownloadFinishedNotifyIfNeed()

    def _ShowDownloadFinishedNotifyIfNeed(self):
        if not self.downloadNotifyActive:
            return
        if self.downloadNotifyPending or self.downloadList or self.downloadingList:
            return

        success = len(self.downloadNotifySuccess)
        fail = len(self.downloadNotifyFail)
        total = success + fail
        if total <= 0:
            self.downloadNotifyActive = False
            return

        if fail <= 0:
            msg = "全部下载完成"
        else:
            msg = "下载成功{}，失败{}".format(success, fail)

        self.downloadNotifyActive = False
        self.downloadNotifyPending.clear()
        self.downloadNotifySuccess.clear()
        self.downloadNotifyFail.clear()
        self._ShowSystemTrayMessage(msg)

    def _ShowSystemTrayMessage(self, msg):
        try:
            from PySide6.QtWidgets import QSystemTrayIcon
            from qt_owner import QtOwner
            tray = getattr(QtOwner().owner, "myTrayIcon", None)
            if tray and QSystemTrayIcon.isSystemTrayAvailable():
                tray.showMessage("JMComic", msg, QSystemTrayIcon.Information, 8000)
                return
            QtOwner().ShowMsg(msg)
        except Exception as es:
            Log.Error(es)

    def UpdateTableItem(self, task):
        return

    def UpdateTaskDB(self, task):
        assert isinstance(task, DownloadItem)
        if task.dirty:
            task.dirty = False
            self.db.AddDownloadDB(task)
        for info in task.epsInfo.values():
            if info.dirty:
                info.dirty = False
            self.db.AddDownloadEpsDB(info)

    def TimeOutHandler(self):
        downloadNum = Setting.MultiNum.value
        addNum = downloadNum - len(self.downloadingList)
        if addNum > 0:
            for task in list(self.downloadList):
                assert isinstance(task, DownloadItem)
                if task.status != task.Waiting:
                    self.downloadList.remove(task)
                    continue
                self.StartItemDownload(task)
                if task.status == task.Downloading:
                    addNum -= 1
                if addNum <= 0:
                    break

        convertNum = config.ConvertThreadNum
        addNum = convertNum - len(self.convertingList)
        if addNum > 0:
            for task in list(self.convertList):
                assert isinstance(task, DownloadItem)
                if task.convertStatus != task.Waiting:
                    self.convertList.remove(task)
                    continue

                self.StartItemConvert(task)
                if task.convertStatus == task.Converting:
                    addNum -= 1
                if addNum <= 0:
                    break

        for task in self.downloadingList:
            assert isinstance(task, DownloadItem)
            task.speedStr = ToolUtil.GetDownloadSize(task.speed) + "/s"
            task.speed = 0
            self.UpdateTableItem(task)
        return

    def StartItemDownload(self, task):
        assert isinstance(task, DownloadItem)
        newStatus = task.DownloadInit()
        self.SetNewStatus(task, newStatus)
        if newStatus != task.Downloading:
            return
        epsIndex, index, savePath, isInit = task.GetDownloadPath()
        self.AddDownloadBook(task.bookId, epsIndex, index, self.DownloadStCallBack, self.DownloadCallBack, self.DownloadCompleteCallBack, task.bookId, savePath=savePath, cleanFlag=task.cleanFlag, isInit=isInit)
        self.UpdateTaskDB(task)
        return

    def DownloadStCallBack(self, data, taskId):
        task = self.downloadDict.get(taskId)
        if not task:
            return
        assert isinstance(task, DownloadItem)
        if task.status != task.Downloading:
            return
        st = data.get("st")
        task.statusMsg = st

        # 获取信息成功， 正式开始下载
        if st == Str.Success:
            maxPic = data.get("maxPic")
            title = data.get("title")
            bookName = data.get("bookName")
            author = data.get("author")
            if not maxPic:
                self.ReloadEmptyEpsInfo(task)
                return
            task.DownloadInitCallBack(bookName, author, title, maxPic)
            self.StartItemDownload(task)
        elif st == Str.SpaceEps:
            # 空白章节
            newStatus = task.SkipCurEps()
            self.SetNewStatus(task, newStatus)
            if newStatus == task.Downloading:
                self.StartItemDownload(task)
        elif st == Str.Cache:
            # 进行下一个图片
            newStatus = task.DownloadSucCallBack()
            self.SetNewStatus(task, newStatus)
            if newStatus == task.Downloading:
                epsIndex, index, savePath, isInit = task.GetDownloadPath()
                self.AddDownloadBook(task.bookId, epsIndex, index, self.DownloadStCallBack, self.DownloadCallBack, self.DownloadCompleteCallBack, task.bookId, savePath=savePath, cleanFlag=task.cleanFlag, isInit=isInit)
            return
        elif st in [Str.Reading, Str.ReadingEps, Str.ReadingPicture, Str.Downloading]:
            task.statusMsg = st
            self.UpdateTableItem(task)
        else:
            self.SetNewStatus(task, task.Error)
        return

    def ReloadEmptyEpsInfo(self, task):
        assert isinstance(task, DownloadItem)
        maxRetry = 3
        if task.emptyEpsRetry >= maxRetry:
            self.SetNewStatus(task, task.Error, Str.SpaceEps)
            self.UpdateTaskDB(task)
            return

        task.emptyEpsRetry += 1
        from tools.book import BookMgr
        from server import req
        bookInfo = BookMgr().GetBook(task.bookId)
        if not bookInfo:
            self.AddHttpTask(req.GetBookInfoReq2(task.bookId), self.ReloadEmptyBookInfoBack, task.bookId)
            return

        epsInfo = bookInfo.pageInfo.epsInfo.get(task.curDownloadEpsId)
        if not epsInfo:
            self.AddHttpTask(req.GetBookInfoReq2(task.bookId), self.ReloadEmptyBookInfoBack, task.bookId)
            return

        epsInfo.pictureUrl.clear()
        epsInfo.pictureName.clear()
        epsInfo.scrambleId = 0
        self.AddHttpTask(req.GetBookEpsInfoReq2(task.bookId, epsInfo.epsId), self.ReloadEmptyEpsInfoBack, task.bookId)

    def ReloadEmptyBookInfoBack(self, raw, bookId):
        task = self.downloadDict.get(str(bookId))
        if not task:
            return
        if raw.get("st") != Status.Ok:
            self.SetNewStatus(task, task.Error, raw.get("st"))
            self.UpdateTaskDB(task)
            return
        self.ReloadEmptyEpsInfo(task)

    def ReloadEmptyEpsInfoBack(self, raw, bookId):
        task = self.downloadDict.get(str(bookId))
        if not task:
            return
        if raw.get("st") != Status.Ok:
            self.SetNewStatus(task, task.Error, raw.get("st"))
            self.UpdateTaskDB(task)
            return
        self.StartItemDownload(task)

    def DownloadCallBack(self, downloadSize, laveFileSize, taskId):
        task = self.downloadDict.get(taskId)
        if not task:
            return
        if task.status != task.Downloading:
            return

        task.downloadLen += downloadSize
        task.speedDownloadLen += downloadSize
        return

    def DownloadCompleteCallBack(self, data, msg, taskId):
        task = self.downloadDict.get(taskId)
        if not task:
            return
        if task.status != task.Downloading:
            return
        if msg == Status.Ok:
            newStatus = task.DownloadSucCallBack()
            self.SetNewStatus(task, newStatus)
            if newStatus == task.Downloading:
                epsId, index, savePath, isInit = task.GetDownloadPath()
                self.AddDownloadBook(task.bookId, epsId, index, self.DownloadStCallBack, self.DownloadCallBack, self.DownloadCompleteCallBack, task.bookId, savePath=savePath, cleanFlag=task.cleanFlag, isInit=isInit)
            self.UpdateTableItem(task)
            self.UpdateTaskDB(task)
        elif msg == Str.SpacePic:
            newStatus = task.DownloadFailCallBack()
            self.SetNewStatus(task, newStatus)
            if newStatus == task.Downloading:
                epsIndex, index, savePath, isInit = task.GetDownloadPath()
                self.AddDownloadBook(task.bookId, epsIndex, index, self.DownloadStCallBack, self.DownloadCallBack,
                                     self.DownloadCompleteCallBack, task.bookId, savePath=savePath,
                                     cleanFlag=task.cleanFlag, isInit=isInit)
            self.UpdateTableItem(task)
            self.UpdateTaskDB(task)
        else:
            self.SetNewStatus(task, task.Error)
        return

    def StartItemConvert(self, task):
        assert isinstance(task, DownloadItem)
        newStatus = task.ConvertInit()
        self.SetNewCovertStatus(task, newStatus)
        if newStatus != task.Converting:
            return
        loadPath, savePath = task.GetConvertPath()
        self.AddConvertTaskByPath(loadPath, savePath, self.AddItemConvertBack, task.bookId, cleanFlag=task.cleanFlag)
        self.UpdateTaskDB(task)
        return

    def AddItemConvertBack(self, data, st, backParam, tick):
        task = self.downloadDict.get(backParam)
        if not task:
            return
        if task.convertStatus != task.Converting:
            return

        assert isinstance(task, DownloadItem)
        if st == Status.Ok:
            newState = task.ConvertSucCallBack(tick)
            self.SetNewCovertStatus(task, newState)
            if newState == task.Converting:
                loadPath, savePath = task.GetConvertPath()
                self.AddConvertTaskByPath(loadPath, savePath, self.AddItemConvertBack, task.bookId, cleanFlag=task.cleanFlag)
            self.UpdateTableItem(task)
            self.UpdateTaskDB(task)
        else:
            self.SetNewCovertStatus(task, task.Error, st)
