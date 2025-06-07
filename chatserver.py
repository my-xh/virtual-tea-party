import socket, asyncore
from asyncore import dispatcher
from asynchat import async_chat
from typing import Optional

PORT = 8080
NAME = 'Virtual Tea Party'


class EndSession(Exception):
    """表示会话结束"""


class CommandHandler:
    """命令处理程序"""

    def unknown(self, session: 'ChatSession', cmd: str):
        session.push(f'Unknown command: {cmd}\r\n'.encode())

    def handle(self, session: 'ChatSession', line: str):
        line = line.strip()
        if not line:
            return
        # 将输入的第一个单词解析成命令
        parts = line.split(' ', 1)
        cmd = parts[0]
        if len(parts) > 1:
            line = parts[1].strip()
        else:
            line = ''
        # 查找以do_为前缀的对应命令的执行方法
        method = getattr(self, f'do_{cmd}', None)
        if callable(method):
            method(session, line)
        else:
            self.unknown(session, cmd)


class Room(CommandHandler):
    """聊天室基类"""

    def __init__(self, server: 'ChatServer'):
        self.server = server
        self.sessions = []

    def add(self, session: 'ChatSession'):
        self.sessions.append(session)

    def remove(self, session: 'ChatSession'):
        self.sessions.remove(session)

    def broadcast(self, data: bytes):
        """向聊天室内的所有用户广播消息"""
        for session in self.sessions:
            session.push(data)

    def do_logout(self, session: 'ChatSession', line: str):
        """执行logout命令"""
        raise EndSession()


class LoginRoom(Room):
    """登录聊天室"""

    @staticmethod
    def tip(session: 'ChatSession'):
        session.push(f'Please log in using "login <nick>" or log out with "logout"\r\n'.encode())

    def unknown(self, session: 'ChatSession', cmd: str):
        self.tip(session)

    def add(self, session: 'ChatSession'):
        super().add(session)
        # 问候语
        session.push(f'Welcome to {self.server.name}!\r\n'.encode())
        self.tip(session)

    def do_login(self, session: 'ChatSession', name: str):
        """执行login命令"""
        if not name:
            # 未输入昵称
            session.push(f'Please enter a nickname\r\n'.encode())
        elif name in self.server.users:
            # 昵称已存在
            session.push(f'The name {name} is taken. Please try again\r\n'.encode())
        else:
            # 昵称可用，成功登录
            session.name = name
            session.enter(self.server.main_room)


class LogoutRoom(Room):
    """登出聊天室"""

    def add(self, session: 'ChatSession'):
        session.push(f'Thank you for using {self.server.name}! Goodbye!\r\n'.encode())
        try:
            # 从用户列表中移除登出用户
            del self.server.users[session.name]
        except KeyError:
            pass


class ChatRoom(Room):
    """主聊天室"""

    def add(self, session: 'ChatSession'):
        # 广播用户进入聊天室的信息
        self.broadcast(f'{session.name} has entered the room.\r\n'.encode())
        super().add(session)
        # 用户进入主聊天室时，将用户名与会话关联起来
        self.server.users[session.name] = session

    def remove(self, session: 'ChatSession'):
        super().remove(session)
        # 广播用户离开聊天室的信息
        self.broadcast(f'{session.name} has left the room.\r\n'.encode())

    def do_say(self, session: 'ChatSession', line: str):
        """执行say命令"""
        self.broadcast(f'{session.name}: {line}\r\n'.encode())

    def do_look(self, session: 'ChatSession', line: str):
        """执行look命令，获取聊天室用户列表"""
        session.push(f'The following are in this room:\r\n'.encode())
        session.push(f'{"-" * 20}\r\n'.encode())
        for user, user_session in self.server.users.items():
            if user_session.room == self:
                session.push(f'{user}\r\n'.encode())
        session.push(f'{"-" * 20}\r\n'.encode())

    def do_who(self, session: 'ChatSession', line: str):
        """执行who命令，获取已登录用户列表"""
        session.push(f'The following are logged in:\r\n'.encode())
        session.push(f'{"-" * 20}\r\n'.encode())
        for user in self.server.users:
            session.push(f'{user}\r\n'.encode())
        session.push(f'{"-" * 20}\r\n'.encode())


class ChatSession(async_chat):
    """聊天会话类"""

    def __init__(self, server: 'ChatServer', sock: 'socket.socket'):
        super().__init__(sock)
        self.set_terminator(b'\r\n')
        self.server = server
        self.name = ''
        self.room: Optional['Room'] = None
        self.data: list[bytes] = []
        # 用户首先进入登录聊天室
        self.enter(LoginRoom(server))

    def enter(self, room: 'Room'):
        # 离开当前房间
        if self.room:
            self.room.remove(self)
        # 进入新的房间
        self.room = room
        room.add(self)

    def handle_close(self):
        # 用户进入登出聊天室
        self.enter(LogoutRoom(self.server))
        super().handle_close()

    def collect_incoming_data(self, data: bytes):
        self.data.append(data)

    def found_terminator(self):
        line = b''.join(self.data)
        self.data = []
        try:
            self.room.handle(self, line.decode())
        except EndSession:
            self.handle_close()


class ChatServer(dispatcher):
    """聊天服务器"""

    def __init__(self, port: int, name: str):
        super().__init__()
        self.name = name
        self.users: dict[str, 'ChatSession'] = {}
        self.main_room = ChatRoom(self)
        self.listen_and_serve(port)

    def listen_and_serve(self, port: int):
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.set_reuse_addr()
        self.bind(('', port))
        self.listen(5)

    def handle_accept(self):
        conn, addr = self.accept()
        ChatSession(self, conn)


if __name__ == '__main__':
    s = ChatServer(PORT, NAME)
    try:
        asyncore.loop()
    except KeyboardInterrupt:
        pass
