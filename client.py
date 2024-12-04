import sys
import socket
import threading
import json
import queue
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QPushButton, QLineEdit, QTextEdit,
                             QLabel, QColorDialog, QInputDialog, QMessageBox,
                             QListView, QStyledItemDelegate)
from PyQt5.QtGui import QPainter, QPen, QColor, QTextDocument, QTextOption
from PyQt5.QtCore import Qt, QPoint, pyqtSignal, QEvent, QCoreApplication, QSize, QMargins, QAbstractListModel

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
        self.setMinimumSize(600, 400)
        self.setStyleSheet("background-color: white;")
        self.lines = []

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.last_point = event.pos()

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton and self.last_point:
            current_point = event.pos()

            # 선 정보 저장
            line = {
                'start': self.last_point,
                'end': current_point,
                'color': self.current_color,
                'width': self.line_width
            }
            self.lines.append(line)

            # 데이터 전송
            data = {
                'type': 'line',
                'x1': self.last_point.x(),
                'y1': self.last_point.y(),
                'x2': current_point.x(),
                'y2': current_point.y(),
                'color': self.current_color.name(),
                'width': self.line_width
            }
            self.line_drawn.emit(data)

            self.last_point = current_point
            self.update()  # paintEvent 호출

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

        line = {
            'start': start,
            'end': end,
            'color': color,
            'width': width
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
        self.setGeometry(100, 100, 900, 600)

        # 메인 위젯과 레이아웃
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QHBoxLayout(main_widget)

        # 왼쪽 프레임 (그림판)
        left_frame = QWidget()
        left_layout = QVBoxLayout(left_frame)

        # 캔버스
        self.canvas = DrawingCanvas()
        self.canvas.line_drawn.connect(self.send_data)
        left_layout.addWidget(self.canvas)

        # 도구 버튼들
        tool_layout = QHBoxLayout()
        self.color_btn = QPushButton('색상 선택')
        self.color_btn.clicked.connect(self.choose_color)
        self.clear_btn = QPushButton('지우기')
        self.clear_btn.clicked.connect(self.clear_canvas)

        tool_layout.addWidget(self.color_btn)
        tool_layout.addWidget(self.clear_btn)
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
        layout.addWidget(left_frame, stretch=2)
        layout.addWidget(right_frame, stretch=1)

    def setupNetwork(self):
        try:
            self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client.connect(('localhost', 3000))

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


if __name__ == '__main__':
    app = QApplication(sys.argv)
    client = DrawingClient()
    client.show()
    sys.exit(app.exec_())
