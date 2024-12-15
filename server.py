import sys
import socket
import threading
import json
import ssl
from datetime import datetime
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QLabel, QTreeWidget, QTreeWidgetItem, QTextEdit, QMenu, QAction, QPushButton)
from PyQt5.QtCore import Qt, QMetaObject, Q_ARG, Qt, pyqtSlot
from PyQt5.QtCore import QTimer
import subprocess


class ServerWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.clients = []
        self.nicknames = []
        self.client_connect_times = {}
        self.ip_toggle_state = False  # IP 표시 상태 추적
        self.initUI()
        self.setupServer()

        # 경과 시간 업데이트를 위한 타이머 설정
        self.elapsed_time_timer = QTimer()
        self.elapsed_time_timer.timeout.connect(self.update_elapsed_times)
        self.elapsed_time_timer.start(1000)  # 1초마다 업데이트

        # 트리 위젯에 컨텍스트 메뉴 설정
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(
            self.show_tree_context_menu)

        # 레이아웃 초기화
        self.layout = QVBoxLayout()  # QVBoxLayout으로 초기화

        # 접속자 수 레이블
        self.count_label = QLabel('현재 접속자 수: 0명')
        self.layout.addWidget(self.count_label)

        # 트리 위젯 설정
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(['닉네임', '접속시간', '포트', '경과시간', '상태'])
        self.tree.setColumnWidth(0, 150)
        self.tree.setColumnWidth(1, 200)
        self.tree.setColumnWidth(2, 100)
        self.tree.setColumnWidth(3, 100)
        self.tree.setColumnWidth(4, 100)
        self.layout.addWidget(self.tree)

        # IP 주소 레이아웃 추가
        ip_layout = QHBoxLayout()
        self.ip_label = QLabel(f"서버 로컬 IP 주소: {self.get_internal_ip()}")
        self.ip_toggle_button = QPushButton("IP 형식 변환")
        self.ip_toggle_button.clicked.connect(self.toggle_ip_format)

        # 서버 종료 버튼 추가
        self.server_shutdown_button = QPushButton("서버 종료")
        self.server_shutdown_button.clicked.connect(self.shutdown_server)

        ip_layout.addWidget(self.ip_label)
        ip_layout.addWidget(self.ip_toggle_button)
        ip_layout.addWidget(self.server_shutdown_button)  # 버튼 추가

        self.layout.addLayout(ip_layout)  # IP 레이아웃 추가

        # 텍스트 박스 추가
        self.netstat_textbox = QTextEdit(self)
        self.netstat_textbox.setReadOnly(True)
        self.layout.addWidget(self.netstat_textbox)  # 텍스트 박스 추가

        # 메인 위젯 설정
        main_widget = QWidget()
        main_widget.setLayout(self.layout)  # 메인 위젯에 레이아웃 설정
        self.setCentralWidget(main_widget)  # 중앙 위젯으로 설정

        # 트리 위젯에 컨텍스트 메뉴 설정
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(
            self.show_tree_context_menu)

        # 초기 netstat 결과 업데이트
        self.update_netstat()

    def initUI(self):
        self.setWindowTitle('그림판 & 채팅 서버')
        self.setGeometry(100, 100, 700, 500)

        # 레이아웃 초기화
        self.layout = QVBoxLayout()  # QVBoxLayout으로 초기화

        # 접속자 수 레이블
        self.count_label = QLabel('현재 접속자 수: 0명')
        self.layout.addWidget(self.count_label)

        # 트리 위젯 설정
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(['닉네임', '접속시간', '포트', '경과시간', '상태'])
        self.tree.setColumnWidth(0, 150)
        self.tree.setColumnWidth(1, 200)
        self.tree.setColumnWidth(2, 100)
        self.tree.setColumnWidth(3, 100)
        self.tree.setColumnWidth(4, 100)
        self.layout.addWidget(self.tree)

        # IP 주소 레이아웃 추가
        ip_layout = QHBoxLayout()
        self.ip_label = QLabel(f"서버 로컬 IP 주소: {self.get_internal_ip()}")
        self.ip_toggle_button = QPushButton("IP 형식 변환")
        self.ip_toggle_button.clicked.connect(self.toggle_ip_format)

        # 서버 종료 버튼 추가
        self.server_shutdown_button = QPushButton("서버 종료")
        self.server_shutdown_button.clicked.connect(self.shutdown_server)

        ip_layout.addWidget(self.ip_label)
        ip_layout.addWidget(self.ip_toggle_button)
        ip_layout.addWidget(self.server_shutdown_button)  # 버튼 추가

        self.layout.addLayout(ip_layout)  # IP 레이아웃 추가

        # 텍스트 박스 추가
        self.netstat_textbox = QTextEdit(self)
        self.netstat_textbox.setReadOnly(True)
        self.layout.addWidget(self.netstat_textbox)  # 텍스트 박스 추가

        # 메인 위젯 설정
        main_widget = QWidget()
        main_widget.setLayout(self.layout)  # 메인 위젯에 레이아웃 설정
        self.setCentralWidget(main_widget)  # 중앙 위젯으로 설정

        # 트리 위젯에 컨텍스트 메뉴 설정
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(
            self.show_tree_context_menu)

        # 초기 netstat 결과 업데이트
        self.update_netstat()

    def setupServer(self):
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.bind(('localhost', 3000))
        self.server.listen(5)
        print("서버가 시작되었습니다...")

        # SSL 컨텍스트 생성
        context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        context.load_cert_chain(
            certfile='auth/certfile.pem', keyfile='auth/keyfile.pem')

        # SSL 소켓으로 래핑
        self.server = context.wrap_socket(self.server, server_side=True)

        # 연결 수락 스레드 시작
        accept_thread = threading.Thread(target=self.accept_connections)
        accept_thread.daemon = True
        accept_thread.start()

    def update_client_count(self):
        # 접속자 수 업데이트
        self.count_label.setText(f"현재 접속자 수: {len(self.clients)}명")

    @pyqtSlot(str, int)
    def add_client_to_tree_slot(self, nickname, port):
        try:
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            connect_time = datetime.now()

            # 클라이언트 접속 시간 저장
            self.client_connect_times[nickname] = connect_time

            item = QTreeWidgetItem([
                nickname,
                current_time,
                str(port),
                "0초",
                "연결됨"
            ])
            self.tree.addTopLevelItem(item)
            self.update_client_count()
        except Exception as e:
            print(f"트리 추가 중 오류: {e}")

    @pyqtSlot(str)
    def remove_client_slot(self, nickname):
        try:
            for i in range(self.tree.topLevelItemCount()):
                item = self.tree.topLevelItem(i)
                if item.text(0) == nickname:
                    item.setText(4, "종료됨")  # 상태 컬럼 인덱스 변경

                    # 클라이언트 접속 시간 제거
                    if nickname in self.client_connect_times:
                        del self.client_connect_times[nickname]

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

                # GUI 업데이트 (포트 번호 추가)
                QMetaObject.invokeMethod(self,
                                         "add_client_to_tree_slot",
                                         Qt.QueuedConnection,
                                         Q_ARG(str, nickname),
                                         Q_ARG(int, address[1]))  # 포트 번호 전달

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
        # 타이머 중지
        self.elapsed_time_timer.stop()

        # 기존 클로즈 이벤트 로직
        for client in self.clients:
            try:
                client.close()
            except:
                pass

        try:
            self.server.close()
        except:
            pass

        event.accept()

    def get_internal_ip(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            internal_ip = s.getsockname()[0]
            s.close()
            return internal_ip
        except OSError as e:
            print(f"내부 IP를 가져오는 중 오류가 발생했습니다: {e}")
            return None

    def toggle_ip_format(self):
        try:
            current_ip = self.ip_label.text().split(": ")[-1]

            if not hasattr(self, 'converted_ip'):
                # 처음 변환 시
                packed_ip = socket.inet_aton(current_ip)
                self.converted_ip = int.from_bytes(packed_ip, byteorder='big')
                self.ip_label.setText(f"서버 로컬 IP 주소(숫자): {self.converted_ip}")
            elif not self.ip_toggle_state:
                # 숫자에서 IP로 변환
                packed_ip = self.converted_ip.to_bytes(4, byteorder='big')
                restored_ip = socket.inet_ntoa(packed_ip)
                self.ip_label.setText(f"서버 로컬 IP 주소: {restored_ip}")
            else:
                # IP에서 숫자로 변환
                packed_ip = socket.inet_aton(current_ip)
                self.converted_ip = int.from_bytes(packed_ip, byteorder='big')
                self.ip_label.setText(f"서버 로컬 IP 주소(숫자): {self.converted_ip}")

            # 상태 토글
            self.ip_toggle_state = not self.ip_toggle_state

        except Exception as e:
            print(f"IP 변환 중 오류: {e}")

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

    def update_elapsed_times(self):
        # 모든 클라이언트의 경과 시간 업데이트
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            nickname = item.text(0)

            if nickname in self.client_connect_times:
                connect_time = self.client_connect_times[nickname]
                elapsed_time = datetime.now() - connect_time

                # hh:mm:ss 형식으로 포맷팅
                hours, remainder = divmod(
                    int(elapsed_time.total_seconds()), 3600)
                minutes, seconds = divmod(remainder, 60)

                elapsed_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"

                item.setText(3, elapsed_str)

        # 트리뷰 업데이트 후 netstat 결과 업데이트
        self.update_netstat()

    def update_netstat(self):
        # netstat 명령 실행
        result = subprocess.run(
            ['netstat', '-an'], capture_output=True, text=True)
        # 3000 포트 관련 결과 필터링
        filtered_result = "\n".join(
            [line for line in result.stdout.splitlines() if '3000' in line])
        # 텍스트 박스에 결과 업데이트
        self.netstat_textbox.setPlainText(filtered_result)

    def show_tree_context_menu(self, pos):
        # 트리 위젯에서 우클릭 시 컨텍스트 메뉴 표시
        item = self.tree.itemAt(pos)
        if item:
            context_menu = QMenu(self)
            disconnect_action = QAction("연결 끊기", self)
            disconnect_action.triggered.connect(
                lambda: self.disconnect_client(item))
            context_menu.addAction(disconnect_action)
            context_menu.exec_(self.tree.mapToGlobal(pos))

    def disconnect_client(self, tree_item):
        # 특정 클라이언트 연결 끊기
        try:
            nickname = tree_item.text(0)

            # 해당 닉네임을 가진 클라이언트 찾기
            for client in self.clients[:]:  # 복사본으로 순회
                client_index = self.clients.index(client)
                if self.nicknames[client_index] == nickname:
                    # 클라이언트 제거 메서드 호출
                    self.remove_client(client, nickname)
                    break
        except Exception as e:
            print(f"클라이언트 연결 끊기 중 오류: {e}")

    def shutdown_server(self):
        try:
            # 모든 클라이언트 연결 종료
            for client in self.clients[:]:
                try:
                    # 클라이언트에게 서버 종료 메시지 전송
                    shutdown_message = {
                        'type': 'server_shutdown',
                        'message': '서버가 종료됩니다.'
                    }
                    client.send(json.dumps(shutdown_message).encode('utf-8'))
                    client.close()
                except Exception as e:
                    print(f"클라이언트 연결 종료 중 오류: {e}")

            # 서버 소켓 종료
            if hasattr(self, 'server'):
                self.server.close()

            # 타이머 중지
            if hasattr(self, 'elapsed_time_timer'):
                self.elapsed_time_timer.stop()

            # 애플리케이션 종료
            QApplication.quit()

        except Exception as e:
            print(f"서버 종료 중 오류: {e}")


if __name__ == '__main__':
    app = QApplication(sys.argv)
    server = ServerWindow()
    server.show()
    sys.exit(app.exec_())
