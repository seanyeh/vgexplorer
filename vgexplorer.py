import argparse
import os
import shutil
import signal
import socket
import subprocess
import sys
import threading

from pathlib import Path

from PyQt5.QtWidgets import QApplication, QFileSystemModel, QMessageBox, QLineEdit, QInputDialog, QShortcut, QTreeView, QWidget, QVBoxLayout, QMenu

from PyQt5 import QtCore
from PyQt5.QtGui import QKeySequence
from PyQt5.QtCore import QDir, QPoint, QUrl, QMimeData

SERVER_PREFIX="/tmp/vgexplorer-"

class Daemon(threading.Thread):
    def __init__(self, server_name, main):
        threading.Thread.__init__(self)
        self.main = main
        self.socket_name = f"{SERVER_PREFIX}{server_name}"

    def run(self):
        if os.path.exists(self.socket_name):
            # TODO: option for confirmation dialog?
            os.unlink(self.socket_name)

        self.server = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        self.server.bind(self.socket_name)

        while True:
            data = self.server.recv(1024)
            if data.decode("utf-8") == "toggle":
                self.main.toggle_show()


class Config:
    def __init__(self, args):
        self.vim = "vim"
        if args.neovim:
            self.vim = "nvr"

        self.is_hidden = False
        self.server_name = args.server_name


class VGExplorer(QWidget):
    def __init__(self, app, config):
        super().__init__()

        self.clipboard = app.clipboard()

        self.config = config
        self.setWindowTitle(config.server_name)

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

        # Ctrl-T hides the window
        # TODO: make shortcut customizable
        self.shortcut = QShortcut(QKeySequence("Ctrl+T"), self)
        self.shortcut.activated.connect(self.hide)

        self.show()

    def toggle_show(self):
        if self.isHidden():
            self.show()
        else:
            self.hide()


    def open_file(self, index):
        path = self.sender().model().filePath(index)
        if os.path.isfile(path):
            subprocess.call([self.config.vim, "--servername", self.config.server_name, "--remote", path])


    def get_cwd(self):
        path = subprocess.check_output([self.config.vim, "--servername", self.config.server_name, "--remote-expr", "getcwd()"])
        return path.decode("utf-8").strip()


    def on_double_click(self, index):
        self.open_file(index)


    def show_menu(self, clickPos):
        index = self.tree.indexAt(clickPos)
        selected_path = self.tree.model().filePath(index)
        enclosing_dir = self.find_enclosing_dir(selected_path)

        menu = QMenu(self)
        openAction = menu.addAction("Open")
        newFolderAction = menu.addAction("New Folder")
        newFileAction = menu.addAction("New File")
        copyAction = menu.addAction("Copy")
        pasteAction = menu.addAction("Paste")
        renameAction = menu.addAction("Rename")
        fileInfo = menu.addAction("Properties")

        menuPos = QPoint(clickPos.x() + 15, clickPos.y() + 15)
        action = menu.exec_(self.mapToGlobal(menuPos))

        if action == openAction:
            self.open_file(index)

        elif action == newFolderAction:
            path = self.get_dialog_str("New Folder", "Enter name for new folder:")
            if path:
                self.mkdir(os.path.join(enclosing_dir, path))

        elif action == newFileAction:
            path = self.get_dialog_str("New File", "Enter name for new file:")
            if path:
                self.touch(os.path.join(enclosing_dir, path))

        elif action == renameAction:
            path = self.get_dialog_str("Rename File", "Enter new name:")

            # Naive validation
            if "/" in path:
                msg = QMessageBox()
                msg.setIcon(QMessageBox.Critical)
                msg.setText("Filename cannot contain '/'")
                msg.setWindowTitle("Error")
                msg.exec_()
                return

            new_path = os.path.join(enclosing_dir, path)

            self.move(selected_path, new_path)

        elif action == copyAction:
            mime_data = QMimeData()

            # TODO: support multiple selections
            mime_data.setUrls([QUrl(Path(selected_path).as_uri())])
            self.clipboard.setMimeData(mime_data)

        elif action == pasteAction:
            mime_data = self.clipboard.mimeData()
            if not mime_data:
                return

            if mime_data.hasUrls():
                for src_url in mime_data.urls():
                    self.copy(src_url.path(), enclosing_dir)


    def get_dialog_str(self, title, message):
        text, confirm = QInputDialog.getText(self, title, message, QLineEdit.Normal, "")
        if confirm and text != '':
            return text
        return None

    '''
    Filesystem and OS Functions
    '''

    def copy(self, src_file, dest_dir):
        src_basename = os.path.basename(src_file)
        dest_file = os.path.join(dest_dir, src_basename)

        # First confirm file doesn't already exist
        if os.path.exists(dest_file):
            print(f"Destination path '{dest_file}' already exists, skipping")
            return

        print(f"Pasting {src_file} -> {dest_file}")
        shutil.copy2(src_file, dest_file)

    def move(self, old_path, new_path):
        os.rename(old_path, new_path)

    def mkdir(self, path):
        if not os.path.exists(path):
            os.mkdir(path)

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


def run_toggle(server_name):
    client = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    client.connect(f"{SERVER_PREFIX}{server_name}")
    client.send("toggle".encode("utf-8"))


def main():
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    parser = argparse.ArgumentParser()
    parser.add_argument("--neovim", action="store_true",
            help="Use neovim instead of vim")

    parser.add_argument("--toggle", action="store_true",
            help="Toggle window")

    parser.add_argument("server_name", metavar="SERVER_NAME",
            help="Server name")

    args = parser.parse_args()

    config = Config(args)

    if args.toggle:
        run_toggle(args.server_name)
        sys.exit(0)

    app = QApplication([])

    vgexplorer = VGExplorer(app, config)

    daemon = Daemon(args.server_name, vgexplorer)
    daemon.start()

    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
