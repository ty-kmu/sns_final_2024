import sys
import socket
import threading
import json
import queue
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QPushButton, QLineEdit, QTextEdit,
                             QLabel, QColorDialog, QInputDialog, QMessageBox)
from PyQt5.QtGui import QPainter, QPen, QColor
from PyQt5.QtCore import Qt, QPoint, pyqtSignal, QEvent, QCoreApplication


class CustomEvent(QEvent):
    """커스텀 이벤트 클래스"""
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
        """원격 클라이언트의 선 그리기"""
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
        """닉네임 입력 대화상자"""
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

        self.chat_box = QTextEdit()
        self.chat_box.setReadOnly(True)
        # 채팅창 스타일 설정
        self.chat_box.setStyleSheet("""
            QTextEdit {
                border: 1px solid #ccc;
                border-radius: 5px;
                padding: 10px;
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
            # sys.exit()

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
        """메인 스레드에서 안전하게 UI 업데이트"""
        QApplication.instance().postEvent(self, CustomEvent(data))

    def send_data(self, data):
        """서버로 데이터를 전송하는 메서드"""
        try:
            self.client.send(json.dumps(data).encode('utf-8'))
        except Exception as e:
            print(f"전송 오류: {e}")

    def send_message(self):
        """채팅 메시지를 전송하는 메서드"""
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
        """프로그램 종료 시 처리"""
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
        """커스텀 이벤트 처리"""
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
        cursor = self.chat_box.textCursor()

        if type == 'join_exit':
            html = f'''<div style="text-align: center; color: #888; margin: 5px;">
            {message}</div><div></div><br>'''
        else:
            if ':' in message:
                nickname, content = message.split(':', 1)
                is_my_message = nickname.strip() == self.nickname
            else:
                is_my_message = False
                content = message

            # margin을 사용하여 말풍선 위치 조정
            margin_style = 'justify-content: flex-start;' if is_my_message else 'justify-content: flex-end;'
            bg_color = '#DCF8C6' if is_my_message else '#E8E8E8'

            html = f'''
                <div style="display: flex; {margin_style}; width: 100%;">
                    <span style="background: {bg_color};
                                padding: 8px 12px;
                                border-radius: 15px;
                                display: inline-block;
                                color: black;
                                word-wrap: break-word;">
                        {message}
                    </span>
                </div><br>
            '''
        cursor.movePosition(cursor.End)
        cursor.insertHtml(html)

        # 스크롤을 항상 최신 메시지로 이동
        self.chat_box.verticalScrollBar().setValue(
            self.chat_box.verticalScrollBar().maximum()
        )


if __name__ == '__main__':
    app = QApplication(sys.argv)
    client = DrawingClient()
    client.show()
    sys.exit(app.exec_())
