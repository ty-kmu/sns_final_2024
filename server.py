import socket
import threading
import json
import tkinter as tk
from tkinter import ttk
from datetime import datetime


class DrawingServer:
    def __init__(self, host='localhost', port=3000):
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.bind((host, port))
        self.server.listen()
        self.clients = []
        self.nicknames = []
        print("서버가 시작되었습니다...")

        # GUI 초기화
        self.setup_gui()

    def setup_gui(self):
        self.root = tk.Tk()
        self.root.title("서버 모니터링")
        self.root.geometry("400x500")

        # 접속자 목록 프레임
        frame = ttk.LabelFrame(self.root, text="접속자 목록")
        frame.pack(padx=10, pady=5, fill="both", expand=True)

        # 접속자 목록 트리뷰
        self.tree = ttk.Treeview(frame, columns=(
            "닉네임", "접속시간", "상태"), show="headings", height=10)
        self.tree.heading("닉네임", text="닉네임")
        self.tree.heading("접속시간", text="접속시간")
        self.tree.heading("상태", text="상태")
        self.tree.column("닉네임", width=100)
        self.tree.column("접속시간", width=150)
        self.tree.column("상태", width=80)
        self.tree.pack(padx=5, pady=5, fill="both", expand=True)

        # 스크롤바 추가
        scrollbar = ttk.Scrollbar(
            frame, orient="vertical", command=self.tree.yview)
        scrollbar.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=scrollbar.set)

        # 서버 상태 프레임
        status_frame = ttk.Frame(self.root)
        status_frame.pack(fill="x", padx=10, pady=5)

        # 서버 상태 레이블
        self.status_label = ttk.Label(status_frame, text="서버 상태: 실행 중")
        self.status_label.pack(side="left", padx=5)

        # 접속자 수 레이블
        self.count_label = ttk.Label(status_frame, text="현재 접속자 수: 0명")
        self.count_label.pack(side="right", padx=5)

        # 주기적으로 GUI 업데이트
        self.update_labels()

        # 상태 체크 타이머 시작
        self.check_connections()

    def update_labels(self):
        # 주기적으로 레이블 업데이트
        self.count_label.config(text=f"현재 접속자 수: {len(self.clients)}명")
        self.root.after(1000, self.update_labels)  # 1초마다 업데이트

    def broadcast(self, message, sender=None):
        for client in self.clients:
            if client != sender:
                try:
                    client.send(message)
                except:
                    self.remove_client(client)
    
    def update_tree(self, nickname):
        try:
            for item in self.tree.get_children():
                if self.tree.item(item)['values'][0] == nickname:
                    # 상태를 '종료됨'으로 변경 후 잠시 대기했다가 삭제
                    self.tree.set(item, "상태", "종료됨")
                    self.root.after(
                        2000, lambda: self.tree.delete(item))
                    break
                self.count_label.config(
                            text=f"현재 접속자 수: {len(self.clients)}명")
        except Exception as e:
            print(f"트리뷰 업데이트 중 오류: {e}")

    def remove_client(self, client, nickname):
        try:
            if client in self.clients:
                self.clients.remove(client)
                self.nicknames.remove(nickname)

                self.root.after(0, self.update_tree(nickname))

                # 퇴장 메시지 브로드캐스트
                exit_message = {
                    'type': 'join_exit',
                    'message': f"{nickname}님이 퇴장하셨습니다."
                }
                self.broadcast(json.dumps(exit_message).encode('utf-8'))

                # 소켓 종료
                try:
                    client.shutdown(socket.SHUT_RDWR)
                except:
                    pass
                finally:
                    client.close()

        except Exception as e:
            print(f"클라이언트 제거 중 오류 발생: {e}")

    def handle_client(self, client, nickname):
        while True:
            try:
                message = client.recv(1024).decode('utf-8')
                if not message:
                    break

                data = json.loads(message)
                if data['type'] == 'exit':
                    self.remove_client(client, nickname)
                    break

                # 다른 메시지 처리...
                self.broadcast(message.encode('utf-8'), client)

            except json.JSONDecodeError:
                print(f"JSON 디코딩 오류: {message}")
                continue
            except Exception as e:
                print(f"클라이언트 처리 중 오류 발생: {e}")
                break

    def start(self):
        self.root.after(100, self.accept_connections)
        self.root.mainloop()

    def add_to_tree(self, nickname):
        print(f"[DEBUG] add_to_tree 호출됨: {nickname}")

        def update():
            try:
                current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                item_id = self.tree.insert("", "end",
                                           values=(nickname, current_time, "연결됨"))
                print(f"[DEBUG] 트리뷰에 항목 추가됨: {item_id}")
                self.tree.see(item_id)
                self.count_label.config(text=f"현재 접속자 수: {len(self.clients)}명")
            except Exception as e:
                print(f"[ERROR] 트리뷰 업데이트 중 오류 발생: {str(e)}")
                import traceback
                traceback.print_exc()

        if not hasattr(self, 'root') or not self.root.winfo_exists():
            print("[ERROR] GUI가 초기화되지 않았거나 이미 종료됨")
            return

        self.root.after_idle(update)

    def accept_connections(self):
        try:
            self.server.settimeout(0.1)
            client, address = self.server.accept()
            print(f"[DEBUG] 새로운 연결 수락: {address}")

            client.send('NICK'.encode('utf-8'))
            nickname = client.recv(1024).decode('utf-8')
            print(f"[DEBUG] 닉네임 받음: {nickname}")

            self.clients.append(client)
            self.nicknames.append(nickname)

            # GUI 업데이트
            self.add_to_tree(nickname)

            join_message = {
                'type': 'join_exit',
                'message': f"{nickname}님이 입장하셨습니다!"
            }
            self.broadcast(json.dumps(join_message).encode('utf-8'))

            thread = threading.Thread(
                target=self.handle_client, args=(client, nickname))
            thread.daemon = True
            thread.start()

        except socket.timeout:
            pass
        except Exception as e:
            print(f"[ERROR] 연결 처리 중 오류 발생: {str(e)}")
            import traceback
            traceback.print_exc()

        finally:
            # 다음 연결 확인을 위해 재귀적으로 호출
            self.root.after(100, self.accept_connections)

    def check_connections(self):
        # 주기적으로 모든 클라이언트의 연결 상태를 확인
        try:
            for item in self.tree.get_children():
                values = self.tree.item(item)['values']
                nickname = values[0]
                if nickname in self.nicknames:
                    index = self.nicknames.index(nickname)
                    client = self.clients[index]

                    try:
                        # 연결 상태 확인을 위한 더미 데이터 전송
                        client.send(b'')
                        self.tree.set(item, "상태", "연결됨")
                    except:
                        self.tree.set(item, "상태", "끊김")
                        # 연결이 끊어진 클라이언트 제거
                        self.remove_client(client, nickname)
        except Exception as e:
            print(f"연결 상태 확인 중 오류: {e}")

        # 1초마다 상태 체크
        self.root.after(1000, self.check_connections)


if __name__ == "__main__":
    server = DrawingServer()
    server.start()

    server.start()
