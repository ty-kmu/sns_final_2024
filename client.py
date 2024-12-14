import os
import sys
import socket
import threading
import json
import queue
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QPushButton, QLineEdit, QTextEdit,
                             QLabel, QColorDialog, QInputDialog, QMessageBox,
                             QListView, QStyledItemDelegate)
from PyQt5.QtGui import QPainter, QPen, QColor, QTextDocument, QTextOption, QPixmap
from PyQt5.QtCore import Qt, QPoint, pyqtSignal, QEvent, QCoreApplication, QSize, QMargins, QAbstractListModel
import ssl

USER_ME = 0  # 자신의 메시지
USER_THEM = 1  # 상대방의 메시지

BUBBLE_COLORS = {USER_ME: "#DCF8C6", USER_THEM: "#E8E8E8"}  # 말풍선 색상
USER_TRANSLATE = {USER_ME: QPoint(20, 0), USER_THEM: QPoint(0, 0)}  # 말풍선 위치 조정

BUBBLE_PADDING = QMargins(10, 5, 20, 5)
TEXT_PADDING = QMargins(25, 15, 45, 15)


class MessageDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        painter.save()
        user, text, msg_type = index.model().data(index, Qt.DisplayRole)

        # join/exit 메시지는 중앙 정렬된 일반 텍스트로 표시
        if msg_type == 'join_exit':
            painter.setPen(Qt.gray)  # 회색 텍스트
            font = painter.font()
            font.setPointSize(12)  # 폰트 크기 조절
            painter.setFont(font)

            textrect = option.rect
            painter.drawText(textrect, Qt.AlignCenter, text)
            painter.restore()
            return

        # 일반 채팅 메시지는 기존 말풍선 스타일로 표시
        trans = USER_TRANSLATE[user]
        painter.translate(trans)

        bubblerect = option.rect.marginsRemoved(BUBBLE_PADDING)
        textrect = option.rect.marginsRemoved(TEXT_PADDING)

        painter.setPen(Qt.NoPen)
        color = QColor(BUBBLE_COLORS[user])
        painter.setBrush(color)
        painter.drawRoundedRect(bubblerect, 15, 15)

        painter.setPen(Qt.black)
        toption = QTextOption()
        toption.setWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)

        doc = QTextDocument()
        doc.setDefaultTextOption(toption)
        doc.setHtml(f'<span style="color: black;">{text}</span>')
        doc.setTextWidth(textrect.width())
        doc.setDocumentMargin(0)

        painter.translate(textrect.topLeft())
        doc.drawContents(painter)
        painter.restore()

    def sizeHint(self, option, index):
        _, text, msg_type = index.model().data(index, Qt.DisplayRole)

        # join/exit 메시지는 더 작은 높이로 설정
        if msg_type == 'join_exit':
            return QSize(option.rect.width(), 30)

        # 일반 채팅 메시지는 기존 크기 계산 방식 사용
        textrect = option.rect.marginsRemoved(TEXT_PADDING)

        toption = QTextOption()
        toption.setWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)

        doc = QTextDocument()
        doc.setDefaultTextOption(toption)
        doc.setHtml(f'<span style="color: black;">{text}</span>')
        doc.setTextWidth(textrect.width())
        doc.setDocumentMargin(0)

        textrect.setHeight(int(doc.size().height()))
        textrect = textrect.marginsAdded(TEXT_PADDING)
        return textrect.size()


class MessageModel(QAbstractListModel):
    def __init__(self):
        super().__init__()
        self.messages = []

    def data(self, index, role):
        if role == Qt.DisplayRole:
            return self.messages[index.row()]

    def rowCount(self, index):
        return len(self.messages)

    def add_message(self, who, text, msg_type='chat'):
        if text:
            self.messages.append((who, text, msg_type))
            self.layoutChanged.emit()


class CustomEvent(QEvent):
    # 커스텀 이벤트 클래스
    EVENT_TYPE = QEvent.Type(QEvent.registerEventType())

    def __init__(self, data):
        super().__init__(CustomEvent.EVENT_TYPE)
        self.data = data


class DrawingCanvas(QWidget):
    line_drawn = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self.last_point = None
        self.current_color = QColor(Qt.black)
        self.line_width = 2
        self.drawing_mode = 'pen'  # 'pen' 또는 'eraser' 모드
        self.setMinimumSize(600, 400)
        self.setStyleSheet("background-color: white;")
        self.lines = []

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.last_point = event.pos()

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton and self.last_point:
            current_point = event.pos()

            # 그리기/지우기 모드에 따라 색상 설정
            color = QColor(
                Qt.white) if self.drawing_mode == 'eraser' else self.current_color

            # 선 정보 저장
            line = {
                'start': self.last_point,
                'end': current_point,
                'color': color,
                'width': 10 if self.drawing_mode == 'eraser' else self.line_width
            }
            self.lines.append(line)

            # 데이터 전송
            data = {
                'type': 'line',
                'x1': self.last_point.x(),
                'y1': self.last_point.y(),
                'x2': current_point.x(),
                'y2': current_point.y(),
                'color': color.name(),
                'width': 10 if self.drawing_mode == 'eraser' else self.line_width,
                'mode': self.drawing_mode
            }
            self.line_drawn.emit(data)

            self.last_point = current_point
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.last_point = None

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # 배경 그리기
        painter.fillRect(self.rect(), Qt.white)

        # 저장된 모든 선 그리기
        for line in self.lines:
            pen = QPen()
            pen.setColor(line['color'])
            pen.setWidth(line['width'])
            pen.setCapStyle(Qt.RoundCap)
            painter.setPen(pen)
            painter.drawLine(line['start'], line['end'])

    def clear(self):
        self.lines.clear()  # 모든 선 지우기
        self.update()

    def draw_remote_line(self, data):
        # 원격 클라이언트의 선 그리기
        start = QPoint(data['x1'], data['y1'])
        end = QPoint(data['x2'], data['y2'])
        color = QColor(data['color'])
        width = data['width']
        mode = data.get('mode', 'pen')  # 모드 정보 추가

        line = {
            'start': start,
            'end': end,
            'color': color,
            'width': width,
            'mode': mode
        }
        self.lines.append(line)
        self.update()


class DrawingClient(QMainWindow):
    def __init__(self):
        super().__init__()
        self.nickname = self.get_nickname()
        if not self.nickname:
            sys.exit()

        self.initUI()
        self.setupNetwork()

    def get_nickname(self):
        # 닉네임 입력 대화상자
        nickname, ok = QInputDialog.getText(None, '닉네임', '닉네임을 입력하세요:')
        if ok and nickname.strip():
            return nickname.strip()
        return None

    def initUI(self):
        self.setWindowTitle('그림판 & 채팅')
        self.setGeometry(100, 100, 1000, 600)

        # 메인 위젯과 레이아웃
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)

        # 상단 정보 라벨 추가
        info_layout = QHBoxLayout()
        self.info_label = QLabel(f'닉네임: {self.nickname} | 포트: ()')
        self.info_label.setStyleSheet('font-weight: bold; padding-left: 10px;')
        info_layout.addWidget(self.info_label)
        layout.addLayout(info_layout)

        # 하위 레이아웃 생성
        content_layout = QHBoxLayout()
        layout.addLayout(content_layout)

        # 왼쪽 프레임 (그림판)
        left_frame = QWidget()
        left_layout = QVBoxLayout(left_frame)

        # 캔버스
        self.canvas = DrawingCanvas()
        self.canvas.line_drawn.connect(self.send_data)
        left_layout.addWidget(self.canvas)

        # 도구 버튼들
        tool_layout = QHBoxLayout()

        self.clear_btn = QPushButton('전체 지우기')
        self.clear_btn.clicked.connect(self.clear_canvas)

        # 자주 사용하는 색상 버튼들 추가
        preset_colors = [
            QColor(Qt.black),     # 검정
            QColor(Qt.red),       # 빨강
            QColor(Qt.blue),      # 파랑
            QColor(Qt.green),     # 초록
            QColor(Qt.yellow),    # 노랑
            QColor(Qt.magenta),   # 자홍
            QColor(Qt.cyan),      # 청록
            QColor(Qt.white),     # 흰색
            QColor(255, 128, 0),  # 주황
            QColor(128, 0, 128)   # 보라
        ]

        self.color_buttons = []
        for color in preset_colors:
            btn = QPushButton()
            btn.setFixedSize(30, 30)

            # 검정색 버튼에는 파란 테두리 추가
            if color == QColor(Qt.black):
                btn.setStyleSheet(f"""
                    background-color: {color.name()};
                    border: 3px solid blue;
                """)
            else:
                btn.setStyleSheet(f"""
                    background-color: {color.name()};
                    border: 1px solid gray;
                """)

            btn.clicked.connect(lambda checked, c=color,
                                b=btn: self.set_preset_color(c, b))
            self.color_buttons.append(btn)

        # 색상 선택 버튼도 동일한 스타일로 변경
        self.color_btn = QPushButton()
        self.color_btn.setFixedSize(30, 30)
        self.color_btn.setStyleSheet(
            "background-color: black; border: 1px solid gray;")
        self.color_btn.clicked.connect(self.choose_color)

        # 색상 선택 아이콘 레이블 생성
        self.color_icon_label = QLabel(self.color_btn)
        self.color_icon_label.setAlignment(Qt.AlignCenter)
        # 아이콘 크기 및 위치 조정
        icon_pixmap = QPixmap(os.path.join(os.path.dirname(
            __file__), 'icons', 'ic_more.png'))  # 아이콘 경로 지정
        scaled_icon = icon_pixmap.scaled(
            20, 20,  # 아이콘 크기
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )
        self.color_icon_label.setPixmap(scaled_icon)
        self.color_icon_label.setGeometry(
            5, 5,  # 위치 조정
            20, 20  # 크기
        )

        tool_layout.addWidget(self.clear_btn)

        # 프리셋 색상 버튼들 추가
        for btn in self.color_buttons:
            tool_layout.addWidget(btn)

        tool_layout.addWidget(self.color_btn)

        # 펜/지우개 모드 전환 버튼 추가
        self.mode_btn = QPushButton('지우개')
        self.mode_btn.setFixedSize(60, 30)  # 버튼 크기 고정
        self.mode_btn.clicked.connect(self.toggle_drawing_mode)
        tool_layout.addWidget(self.mode_btn)

        left_layout.addLayout(tool_layout)

        # 오른쪽 프레임 (채팅)
        right_frame = QWidget()
        right_layout = QVBoxLayout(right_frame)

        self.chat_box = QListView()
        self.chat_box.setItemDelegate(MessageDelegate())
        self.message_model = MessageModel()
        self.chat_box.setModel(self.message_model)
        self.chat_box.setSpacing(2)  # 메시지 간 간격 설정

        # 스타일 설정
        self.chat_box.setStyleSheet("""
            QListView {
                border: 1px solid #ccc;
                border-radius: 5px;
                padding: 5px;
                background: white;
            }
        """)
        right_layout.addWidget(self.chat_box)

        # 메시지 입력
        msg_layout = QHBoxLayout()
        self.msg_input = QLineEdit()
        self.msg_input.returnPressed.connect(self.send_message)
        self.send_btn = QPushButton('전송')
        self.send_btn.clicked.connect(self.send_message)

        msg_layout.addWidget(self.msg_input)
        msg_layout.addWidget(self.send_btn)
        right_layout.addLayout(msg_layout)

        # 메인 레이아웃에 추가
        content_layout.addWidget(left_frame, stretch=2)
        content_layout.addWidget(right_frame, stretch=1)

    def setupNetwork(self):
        try:
            self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client.connect(('localhost', 3000))

            # SSL 컨텍스트 생성
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE

            # SSL 소켓으로 래핑
            self.client = context.wrap_socket(
                self.client, server_hostname='localhost')

            # 서버에서 할당된 포트 번호 가져오기
            local_port = self.client.getsockname()[1]

            # 정보 라벨 업데이트
            self.info_label.setText(f'닉네임: {self.nickname} | 포트: {local_port}')

            # 닉네임 처리
            response = self.client.recv(1024).decode('utf-8')
            if response == 'NICK':
                self.client.send(self.nickname.encode('utf-8'))

            # threading.Thread 사용
            self.network_thread = threading.Thread(target=self.receive)
            self.network_thread.daemon = True
            self.network_thread.start()

        except Exception as e:
            self.handle_received_message(
                {'type': 'err', 'message': '서버 실행 여부를 확인하세요.'})
            self.handle_error(str(e))

    def receive(self):
        buffer = ""
        while True:
            try:
                data = self.client.recv(1024).decode('utf-8')
                if not data:
                    print("서버와의 연결이 끊어졌습니다.")
                    break

                buffer += data
                while True:
                    try:
                        json_end = buffer.find('}')
                        if json_end == -1:
                            break

                        message = buffer[:json_end + 1]
                        buffer = buffer[json_end + 1:]

                        data = json.loads(message)
                        # QThread가 아니므로 직접 호출
                        self.handle_received_message(data)

                    except json.JSONDecodeError:
                        break

            except Exception as e:
                print(f"수신 오류: {e}")
                break

        print("수신 스레드가 종료되었습니다.")
        # 프로그램 종료 알림
        self.handle_received_message(
            {'type': 'err', 'message': '서버와의 연결이 끊어졌습니다.'})

        # sys.exit()

    def handle_received_message(self, data):
        # 메인 스레드에서 안전하게 UI 업데이트
        QApplication.instance().postEvent(self, CustomEvent(data))

    def send_data(self, data):
        # 서버로 데이터를 전송하는 메서드
        try:
            self.client.send(json.dumps(data).encode('utf-8'))
        except Exception as e:
            print(f"전송 오류: {e}")

    def send_message(self):
        # 채팅 메시지를 전송하는 메서드
        message = self.msg_input.text().strip()
        if message:
            data = {
                'type': 'chat',
                'message': f"{self.nickname}: {message}"
            }
            self.send_data(data)
            self.msg_input.clear()

    def choose_color(self):
        color = QColorDialog.getColor()
        if color.isValid():
            # 모든 버튼의 테두리 초기화
            for btn in self.color_buttons:
                btn.setStyleSheet(f"""
                    background-color: {btn.palette().color(btn.backgroundRole()).name()};
                    border: 1px solid gray;
                """)

            # 색상 선택 버튼에 강조 테두리 추가
            self.color_btn.setStyleSheet(f"""
                background-color: {color.name()};
                border: 3px solid blue;
            """)

            self.canvas.current_color = color

    def clear_canvas(self):
        self.canvas.clear()
        data = {'type': 'clear'}
        self.send_data(data)

    def handle_error(self, error_msg):
        print(f"오류 발생: {error_msg}")

    def closeEvent(self, event):
        # 프로그램 종료 시 처리
        try:
            exit_data = {
                'type': 'exit',
                'nickname': self.nickname
            }
            self.send_data(exit_data)
            self.client.close()
        except:
            pass
        event.accept()

    def event(self, event):
        # 커스텀 이벤트 처리
        if event.type() == CustomEvent.EVENT_TYPE:
            data = event.data
            if data['type'] == 'line':
                # 모드 정보 추가
                data['mode'] = data.get('mode', 'pen')
                self.canvas.draw_remote_line(data)
            elif data['type'] == 'chat':
                self.display_chat_message(data['message'], data['type'])
            elif data['type'] == 'clear':
                self.canvas.clear()
            elif data['type'] == 'join_exit':
                self.display_chat_message(data['message'], data['type'])
            elif data['type'] == 'err':
                self.show_error_message(data['message'])
            return True
        return super().event(event)

    def show_error_message(self, message):
        QMessageBox.warning(self, '오류', message)
        QCoreApplication.instance().quit()

    def display_chat_message(self, message, type):
        if type == 'join_exit':
            self.message_model.add_message(USER_THEM, message, 'join_exit')
        else:
            if ':' in message:
                nickname, content = message.split(':', 1)
                is_my_message = nickname.strip() == self.nickname
                who = USER_ME if is_my_message else USER_THEM
                content = content if is_my_message else message
            else:
                who = USER_THEM
                content = message

            self.message_model.add_message(who, content, 'chat')

        self.chat_box.scrollToBottom()

    def set_preset_color(self, color, button):
        # 모든 버튼의 테두리 초기화
        for btn in self.color_buttons:
            btn.setStyleSheet(f"""
                background-color: {btn.palette().color(btn.backgroundRole()).name()};
                border: 1px solid gray;
            """)

        # 선택된 버튼에 강조 테두리 추가
        button.setStyleSheet(f"""
            background-color: {color.name()};
            border: 3px solid blue;
        """)

        # 캔버스 색상 변경
        self.canvas.current_color = color

    def toggle_drawing_mode(self):
        if self.canvas.drawing_mode == 'pen':
            self.canvas.drawing_mode = 'eraser'
            self.mode_btn.setText('펜')
        else:
            self.canvas.drawing_mode = 'pen'
            self.mode_btn.setText('지우개')


if __name__ == '__main__':
    app = QApplication(sys.argv)
    client = DrawingClient()
    client.show()
    sys.exit(app.exec_())
