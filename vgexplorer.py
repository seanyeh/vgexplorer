import os
import signal
import subprocess
import sys

from pathlib import Path

from PyQt5.QtWidgets import QApplication, QFileSystemModel, QLineEdit, QInputDialog, QTreeView, QWidget, QVBoxLayout, QMenu

from PyQt5 import QtCore
from PyQt5.QtCore import QDir, QPoint

class VGExplorer(QWidget):
    def __init__(self, server_name):
        super().__init__()
        self.server_name = server_name

        self.setWindowTitle(server_name)

        rootPath = self.get_cwd()

        self.model = QFileSystemModel()
        index = self.model.setRootPath(rootPath)

        self.tree = QTreeView()
        self.tree.setModel(self.model)

        self.tree.setRootIndex(index)

        self.tree.setAnimated(False)
        self.tree.setIndentation(20)

        self.tree.hideColumn(1)
        self.tree.hideColumn(2)
        self.tree.hideColumn(3)
        self.tree.setHeaderHidden(True)

        self.tree.doubleClicked.connect(self.on_double_click)
        self.tree.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.show_menu)

        windowLayout = QVBoxLayout()
        windowLayout.addWidget(self.tree)
        self.setLayout(windowLayout)

        self.show()


    def open_file(self, index):
        path = self.sender().model().filePath(index)
        if os.path.isfile(path):
            subprocess.call(["vim", "--servername", self.server_name, "--remote", path])


    def get_cwd(self):
        print("server name: " + self.server_name)
        path = subprocess.check_output(["vim", "--servername", self.server_name, "--remote-expr", "getcwd()"])
        return path.decode("utf-8").strip()


    def on_double_click(self, index):
        self.open_file(index)


    def show_menu(self, clickPos):
        index = self.tree.indexAt(clickPos)
        selectedPath = self.tree.model().filePath(index)

        menu = QMenu(self)
        openAction = menu.addAction("Open")
        newAction = menu.addAction("New File")
        copyAction = menu.addAction("Copy")
        pasteAction = menu.addAction("Paste")
        fileInfo = menu.addAction("Properties")

        menuPos = QPoint(clickPos.x() + 15, clickPos.y() + 15)
        action = menu.exec_(self.mapToGlobal(menuPos))

        if action == openAction:
            self.open_file(index)

        elif action == newAction:
            enclosing_dir = self.find_enclosing_dir(selectedPath)
            path = self.get_dialog_str("New File", "Enter name for new file:")
            if path:
                self.touch(os.path.join(enclosing_dir, path))

    def get_dialog_str(self, title, message):
        text, confirm = QInputDialog.getText(self, title, message, QLineEdit.Normal, "")
        if confirm and text != '':
            return text
        return None

    '''
    Filesystem and OS Functions
    '''

    def touch(self, path):
        subprocess.run(["touch", path])

    def find_enclosing_dir(self, path):
        '''
        If path is file, return dir it is in
        If path is dir, return itself
        '''
        if os.path.isdir(path):
            return path

        if os.path.isfile(path):
            return str(Path(path).parent)

    def save_clipboard(self, text):
        if sys.platform == "linux" or sys.platform == "linux2":
            subprocess.run(["xclip", "-sel", "clipboard"], input=text, encoding="utf-8")
        elif sys.platform == "darwin":
            subprocess.run(["pbcopy"], input=text, encoding="utf-8")

    def get_clipboard(self):
        if sys.platform == "linux" or sys.platform == "linux2":
            output = subprocess.check_output(["xclip", "-out", "-sel", "clipboard"])
        elif sys.platform == "darwin":
            output = subprocess.check_output.run(["pbpaste"])
        else:
            return None

        return output.decode("utf-8")


def main():
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    app = QApplication([])
    asdf = VGExplorer(sys.argv[1])
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
