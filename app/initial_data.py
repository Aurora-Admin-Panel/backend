#!/usr/bin/env python3
from getpass import getpass

from app.db.session import db_session
from app.db.crud.user import create_user
from app.db.schemas.user import UserCreate


def init() -> None:
    email = input("请输入管理员邮箱：")
    if not email or "@" not in email:
        print(" 邮箱格式不正确　！")
        return
    password = getpass("请输入密码：")
    if len(password) < 8:
        print("密码长度必须不少于8位，否则无法登录！")
        return
    repeated_password = getpass("请再次输入密码：")
    if password != repeated_password:
        print("两次密码不一致！")
        return

    with db_session() as db:
        create_user(
            db,
            UserCreate(
                email=email,
                password=password,
                is_active=True,
                is_superuser=True,
            ),
        )


if __name__ == "__main__":
    print("Creating superuser")
    init()
    print("Superuser created")
