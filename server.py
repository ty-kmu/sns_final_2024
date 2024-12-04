import sys
import socket
import threading
import json
from datetime import datetime
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QLabel, QTreeWidget, QTreeWidgetItem, QTextEdit)
from PyQt5.QtCore import Qt, QMetaObject, Q_ARG, Qt, pyqtSlot
from PyQt5.QtCore import QTimer


class ServerWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.clients = []
        self.nicknames = []
        self.initUI()
        self.setupServer()

    def initUI(self):
        self.setWindowTitle('그림판 & 채팅 서버')
        self.setGeometry(100, 100, 600, 400)

        # 메인 위젯과 레이아웃
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)

        # 접속자 수 레이블
        self.count_label = QLabel('현재 접속자 수: 0명')
        layout.addWidget(self.count_label)

        # 트리 위젯 설정
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(['닉네임', '접속시간', '상태'])
        self.tree.setColumnWidth(0, 150)
        self.tree.setColumnWidth(1, 200)
        self.tree.setColumnWidth(2, 100)
        layout.addWidget(self.tree)

        self.info = QTextEdit()
        self.info.setReadOnly(True)
        self.info.append(f"서버 로컬 IP 주소: {self.get_internal_ip()}")
        layout.addWidget(self.info)

    def setupServer(self):
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.bind(('localhost', 3000))
        self.server.listen(5)
        print("서버가 시작되었습니다...")

        # 연결 수락 스레드 시작
        accept_thread = threading.Thread(target=self.accept_connections)
        accept_thread.daemon = True
        accept_thread.start()

    def update_client_count(self):
        # 접속자 수 업데이트
        self.count_label.setText(f"현재 접속자 수: {len(self.clients)}명")

    @pyqtSlot(str)
    def add_client_to_tree_slot(self, nickname):
        # 클라이언트를 트리에 추가하는 슬롯
        try:
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            item = QTreeWidgetItem([nickname, current_time, "연결됨"])
            self.tree.addTopLevelItem(item)
            self.update_client_count()
        except Exception as e:
            print(f"트리 추가 중 오류: {e}")

    @pyqtSlot(str)
    def remove_client_slot(self, nickname):
        # 클라이언트를 트리에서 제거하는 슬롯
        try:
            for i in range(self.tree.topLevelItemCount()):
                item = self.tree.topLevelItem(i)
                if item.text(0) == nickname:
                    item.setText(2, "종료됨")
                    # 2초 후에 항목 삭제하고 카운트 업데이트
                    QTimer.singleShot(2000, lambda: self.delayed_remove(i))
                    break
            self.update_client_count()
        except Exception as e:
            print(f"트리 제거 중 오류: {e}")

    def delayed_remove(self, index):
        # 지연된 트리 항목 제거
        try:
            self.tree.takeTopLevelItem(index)
            self.update_client_count()
        except Exception as e:
            print(f"지연 제거 중 오류: {e}")

    def remove_client(self, client, nickname):
        try:
            if client in self.clients:
                # GUI 업데이트를 메인 스레드에서 실행
                QMetaObject.invokeMethod(self,
                                         "remove_client_slot",
                                         Qt.QueuedConnection,
                                         Q_ARG(str, nickname))

                # 클라이언트 리스트에서 제거
                self.clients.remove(client)
                if nickname in self.nicknames:
                    self.nicknames.remove(nickname)

                # 퇴장 메시지 브로드캐스트
                exit_message = {
                    'type': 'join_exit',
                    'message': f"{nickname}님이 퇴장하셨습니다."
                }
                self.broadcast(json.dumps(exit_message).encode('utf-8'))

                try:
                    client.shutdown(socket.SHUT_RDWR)
                except:
                    pass
                finally:
                    client.close()

        except Exception as e:
            print(f"클라이언트 제거 중 오류: {e}")

    def accept_connections(self):
        while True:
            try:
                client, address = self.server.accept()
                print(f"새로운 연결: {address}")

                # 닉네임 요청
                client.send('NICK'.encode('utf-8'))
                nickname = client.recv(1024).decode('utf-8').strip()

                # JSON 형식인지 확인하고, JSON이면 닉네임만 추출
                try:
                    data = json.loads(nickname)
                    if isinstance(data, dict) and 'nickname' in data:
                        nickname = data['nickname']
                except json.JSONDecodeError:
                    pass

                self.clients.append(client)
                self.nicknames.append(nickname)

                # GUI 업데이트
                QMetaObject.invokeMethod(self,
                                         "add_client_to_tree_slot",
                                         Qt.QueuedConnection,
                                         Q_ARG(str, nickname))

                # 입장 메시지 브로드캐스트
                join_message = {
                    'type': 'join_exit',
                    'message': f"{nickname}님이 입장하셨습니다!"
                }
                self.broadcast(json.dumps(join_message).encode('utf-8'))

                # 클라이언트 처리 스레드 시작
                thread = threading.Thread(target=self.handle_client,
                                          args=(client, nickname))
                thread.daemon = True
                thread.start()

            except Exception as e:
                print(f"연결 수락 중 오류: {e}")
                break

    def broadcast(self, message, exclude=None):
        for client in self.clients:
            if client != exclude:
                try:
                    client.send(message)
                except:
                    pass

    def closeEvent(self, event):
        # 모든 클라이언트 연결 종료
        for client in self.clients:
            try:
                client.close()
            except:
                pass

        # 서버 소켓 종료
        try:
            self.server.close()
        except:
            pass

        event.accept()

    def get_internal_ip(self):
        try:
            # 소켓을 생성하고 외부 사이트(예: Google DNS 서버)에 연결 시도
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            # 소켓에 바인딩된 IP 주소 가져오기
            internal_ip = s.getsockname()[0]
            s.close()
            return internal_ip
        except OSError as e:
            print(f"내부 IP를 가져오는 중 오류가 발생했습니다: {e}")
            return None

    def handle_client(self, client, nickname):
        # 클라이언트의 메시지를 처리하는 메서드
        while True:
            try:
                message = client.recv(1024).decode('utf-8')
                if not message:
                    break

                try:
                    # JSON 메시지 파싱
                    data = json.loads(message)
                    # 모든 클라이언트에게 메시지 전달
                    self.broadcast(json.dumps(data).encode('utf-8'))
                except json.JSONDecodeError:
                    print(f"잘못된 JSON 형식: {message}")

            except Exception as e:
                print(f"클라이언트 처리 중 오류: {e}")
                break

        # 연결이 끊어진 경우 클라이언트 제거
        self.remove_client(client, nickname)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    server = ServerWindow()
    server.show()
    sys.exit(app.exec_())
