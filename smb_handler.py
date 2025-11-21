#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SMB操作处理器
基于Impacket库实现SMB客户端功能
"""

import logging
import io
import os
import datetime
from impacket.smbconnection import (
    SMBConnection,
    SMB_DIALECT,
    SMB2_DIALECT_002,
    SMB2_DIALECT_21,
)
from impacket.nmb import NetBIOSError
from impacket.examples.utils import parse_target

logger = logging.getLogger(__name__)


class SMBHandler:
    """SMB操作处理器"""

    def __init__(self):
        self.smb = None
        self.connected = False
        self.domain = None
        self.username = None
        self.password = None
        self.host = None
        self.address = None
        self.port = None
        self.lmhash = None
        self.nthash = None
        self.session = None
        self.smb_version = None
        self.current_share = None
        self.current_path = "\\"

    def connect(self, connection_string):
        """
        使用连接字符串连接到SMB服务器

        Args:
            connection_string (str): SMB连接字符串，如 "administrator:password@server" 或 "DOMAIN\\user:pass@server:port"

        Returns:
            dict: 连接结果
        """
        try:
            logger.info(f"使用连接字符串连接: {connection_string}")

            # 使用impacket的parse_target解析连接字符串
            self.domain, self.username, self.password, self.address = parse_target(
                connection_string
            )
            self.port = 445  # 默认端口

            if self.password is None:
                # 如果没有密码，可能是哈希认证
                self.lmhash, self.nthash = "", ""
            else:
                self.lmhash, self.nthash = "", ""

            logger.info(
                f"解析结果 - 域: {self.domain}, 用户: {self.username}, 地址: {self.address}"
            )

            # 创建SMB连接
            logger.info(f"连接到SMB服务器 {self.address}:{self.port}")
            self.smb = SMBConnection(self.address, self.address, None, self.port)

            # 检测SMB版本
            dialect = self.smb.getDialect()
            if dialect == SMB_DIALECT:
                self.smb_version = "SMBv1"
            elif dialect == SMB2_DIALECT_002:
                self.smb_version = "SMBv2.0"
            elif dialect == SMB2_DIALECT_21:
                self.smb_version = "SMBv2.1"
            else:
                self.smb_version = "SMBv3.0"

            logger.info(f"SMB版本: {self.smb_version}")

            # 登录
            self.smb.login(
                self.username, self.password, self.domain, self.lmhash, self.nthash
            )

            # 检查会话类型
            if self.smb.isGuestSession() > 0:
                self.session = "guest session"
                logger.info("以guest session登录")
            else:
                self.session = "user session"
                logger.info("以user session登录")

            self.connected = True
            logger.info(f"成功连接到SMB服务器: {self.address}")

            return {"success": True, "message": "连接成功"}

        except NetBIOSError as e:
            error_msg = f"网络连接错误: {str(e)}"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}
        except OSError as e:
            error_msg = f"系统错误: {str(e)}"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}
        except Exception as e:
            error_msg = f"连接失败: {str(e)}"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}

    def list_directory(self, path="\\"):
        """
        列出目录内容

        Args:
            path (str): 目录路径

        Returns:
            dict: 列表结果
        """
        try:
            if not self.connected:
                return {"success": False, "error": "未连接到服务器"}

            # 规范化路径
            path = path.replace("/", "\\")
            if not path.startswith("\\"):
                path = "\\" + path
            if not path.endswith("\\"):
                path = path + "\\"

            logger.info(f"列出目录内容: {path}")

            # 获取共享列表
            if path == "\\" or path == "\\\\":
                return self._list_shares()

            # 解析路径，提取共享名称和相对路径
            share_name, relative_path = self._parse_path(path)
            logger.info(f"解析结果 - 共享名: {share_name}, 相对路径: {relative_path}")

            if not share_name:
                return {"success": False, "error": "无效的路径格式"}

            # 设置当前共享和路径
            self.current_share = share_name
            self.current_path = relative_path if relative_path else "\\"

            # 连接到共享并列出内容
            try:
                # 连接到共享
                tree_id = self.smb.connectTree(share_name)
                logger.info(f"成功连接到共享: {share_name}")

                # 如果相对路径为空，设为根目录
                if not relative_path or relative_path == "\\" or relative_path == "/":
                    list_path = "*"
                else:
                    # 确保路径格式正确
                    list_path = relative_path.strip("\\/") + "\\*"

                logger.info(f"使用listPath列出: {share_name}\\{list_path}")

                # 获取文件/目录列表
                file_list = self.smb.listPath(share_name, list_path)
                logger.info(f"listPath返回 {len(file_list)} 个项目")

                # 处理每个文件/目录
                files = []
                for file_item in file_list:
                    if file_item.get_longname() in [".", ".."]:
                        continue

                    # Windows FILETIME转换处理
                    try:
                        # Windows FILETIME转换
                        timestamp = file_item.get_mtime()
                        if timestamp > 100000000000000000:
                            # Windows FILETIME转换为Unix时间戳
                            unix_timestamp = (timestamp - 116444736000000000) / 10000000
                            formatted_time = datetime.datetime.fromtimestamp(
                                unix_timestamp
                            ).strftime("%Y-%m-%d %H:%M:%S")
                        else:
                            # 尝试直接转换
                            formatted_time = datetime.datetime.fromtimestamp(
                                timestamp / 100000000
                            ).strftime("%Y-%m-%d %H:%M:%S")
                    except:
                        formatted_time = "Unknown"

                    file_info = {
                        "name": file_item.get_longname(),
                        "size": file_item.get_filesize(),
                        "is_directory": file_item.is_directory(),
                        "modified_time": formatted_time,
                        "created_time": formatted_time,  # 使用相同的时间
                        "attributes": (
                            str(file_item.get_attributes())
                            if hasattr(file_item, "get_attributes")
                            else "Unknown"
                        ),
                    }
                    files.append(file_info)
                    logger.info(
                        f"添加文件: {file_info['name']} ({'目录' if file_info['is_directory'] else '文件'})"
                    )

                # 文件夹前置排序
                files.sort(key=lambda x: (not x["is_directory"], x["name"]))

                return {"success": True, "files": files}

            except Exception as e:
                logger.error(f"连接共享或列出文件失败: {e}")
                return {"success": False, "error": f"操作失败: {str(e)}"}

        except Exception as e:
            error_msg = f"列出目录失败: {str(e)}"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}

    def _list_shares(self):
        """列出可用的共享"""
        try:
            logger.info("开始获取共享列表")

            # 使用listShares方法
            shares = self.smb.listShares()
            logger.info(f"listShares返回 {len(shares)} 个共享")

            share_list = []
            for share in shares:
                # 处理共享名称
                if hasattr(share, "shi1_netname"):
                    share_name = share["shi1_netname"][:-1]  # 移除结尾的null字符
                    if share_name and not share_name.endswith("$"):  # 过滤掉系统共享
                        share_info = {
                            "name": share_name,
                            "type": "共享文件夹",
                            "is_directory": True,
                            "size": 0,
                            "modified_time": "",
                            "attributes": "SHARE",
                        }
                        share_list.append(share_info)
                        logger.info(f"添加共享: {share_name}")

            # 如果没有共享，添加默认共享
            if not share_list:
                logger.info("没有找到共享，添加默认共享")
                default_shares = ["C$", "D$", "ADMIN$"]
                for share_name in default_shares:
                    share_info = {
                        "name": share_name,
                        "type": "默认共享",
                        "is_directory": True,
                        "size": 0,
                        "modified_time": "",
                        "attributes": "DEFAULT",
                    }
                    share_list.append(share_info)

            # 文件夹前置排序
            share_list.sort(key=lambda x: x["name"])

            logger.info(f"最终获取到 {len(share_list)} 个共享")
            return {"success": True, "files": share_list}

        except Exception as e:
            error_msg = f"获取共享列表失败: {str(e)}"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}

    def _parse_path(self, path):
        """
        解析SMB路径，提取共享名称和相对路径

        Args:
            path (str): 完整的SMB路径，如 \\C$\folder\file

        Returns:
            tuple: (share_name, relative_path)
        """
        try:
            # 标准化路径，确保以\开头
            if not path.startswith("\\"):
                path = "\\" + path

            # 移除开头的反斜杠进行解析
            clean_path = path.strip("\\")

            if not clean_path:
                return None, None

            # 分割路径，第一个部分是共享名
            path_parts = clean_path.split("\\", 1)

            share_name = path_parts[0]
            relative_path = path_parts[1] if len(path_parts) > 1 else ""

            logger.info(
                f"路径解析 - 原路径: {path}, 清理后: {clean_path}, 共享名: {share_name}, 相对路径: {relative_path}"
            )

            return share_name, relative_path

        except Exception as e:
            logger.error(f"解析路径失败: {e}")
            return None, None

    def download_file(self, share_name, file_path, local_path=None):
        """
        下载文件

        Args:
            share_name (str): 共享名称
            file_path (str): 文件路径
            local_path (str): 本地保存路径，如果为None则返回文件内容

        Returns:
            dict: 下载结果
        """
        try:
            if not self.connected or not self.smb:
                return {"success": False, "error": "未连接到服务器"}

            logger.info(f"下载文件: {share_name}\\{file_path}")

            # 连接到共享
            try:
                tree_id = self.smb.connectTree(share_name)
                logger.info(f"成功连接到共享: {share_name}")
            except Exception as e:
                return {
                    "success": False,
                    "error": f"无法连接到共享 {share_name}: {str(e)}",
                }

            # 创建内存文件对象
            if local_path:
                # 保存到本地文件
                with open(local_path, "wb") as f:
                    self.smb.getFile(share_name, file_path, f.write)
                logger.info(f"文件保存到: {local_path}")
                return {
                    "success": True,
                    "file_path": local_path,
                    "size": os.path.getsize(local_path),
                }
            else:
                # 返回文件内容
                fh = io.BytesIO()
                self.smb.getFile(share_name, file_path, fh.write)
                file_data = fh.getvalue()
                fh.close()

                logger.info(f"成功读取文件，大小: {len(file_data)} 字节")
                return {"success": True, "data": file_data, "size": len(file_data)}

        except Exception as e:
            error_msg = f"下载文件失败: {str(e)}"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}

    def upload_file(self, share_name, file_path, file_data):
        """
        上传文件

        Args:
            share_name (str): 共享名称
            file_path (str): 目标文件路径
            file_data (bytes): 文件数据

        Returns:
            dict: 上传结果
        """
        try:
            if not self.connected or not self.smb:
                return {"success": False, "error": "未连接到服务器"}

            logger.info(
                f"上传文件: {share_name}\\{file_path}, 大小: {len(file_data)} 字节"
            )

            # 连接到共享
            try:
                tree_id = self.smb.connectTree(share_name)
                logger.info(f"成功连接到共享: {share_name}")
            except Exception as e:
                return {
                    "success": False,
                    "error": f"无法连接到共享 {share_name}: {str(e)}",
                }

            # 创建内存文件对象
            memory_file = io.BytesIO()
            memory_file.write(file_data)
            memory_file.seek(0)

            # 上传文件
            self.smb.putFile(share_name, file_path, memory_file.read)
            memory_file.close()

            logger.info(f"成功上传文件，大小: {len(file_data)} 字节")

            return {"success": True, "size": len(file_data)}

        except Exception as e:
            error_msg = f"上传文件失败: {str(e)}"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}

    def delete_file(self, share_name, file_path):
        """
        删除文件

        Args:
            share_name (str): 共享名称
            file_path (str): 文件路径

        Returns:
            dict: 删除结果
        """
        try:
            if not self.connected or not self.smb:
                return {"success": False, "error": "未连接到服务器"}

            logger.info(f"删除文件: {share_name}\\{file_path}")

            # 连接到共享
            self.smb.connectTree(share_name)

            # 统一路径格式
            normalized_path = file_path.replace("/", "\\").lstrip("\\")

            # 删除文件
            self.smb.deleteFile(share_name, normalized_path)
            logger.info("文件删除成功")

            return {"success": True, "message": "文件已删除"}

        except Exception as e:
            error_msg = f"删除文件失败: {str(e)}"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}

    def get_file_info(self, share_name, file_path):
        """
        获取文件详细信息

        Args:
            share_name (str): 共享名称
            file_path (str): 文件路径

        Returns:
            dict: 文件信息
        """
        try:
            if not self.connected or not self.smb:
                return {"success": False, "error": "未连接到服务器"}

            # 连接到共享
            tree_id = self.smb.connectTree(share_name)

            # 列出指定文件的信息
            file_list = self.smb.listPath(share_name, file_path)

            if not file_list:
                return {"success": False, "error": f"文件不存在: {file_path}"}

            file_obj = file_list[0]

            # 处理时间戳
            try:
                timestamp = file_obj.get_mtime()
                if timestamp > 100000000000000000:
                    unix_timestamp = (timestamp - 116444736000000000) / 10000000
                    formatted_time = datetime.datetime.fromtimestamp(
                        unix_timestamp
                    ).strftime("%Y-%m-%d %H:%M:%S")
                else:
                    formatted_time = datetime.datetime.fromtimestamp(
                        timestamp / 100000000
                    ).strftime("%Y-%m-%d %H:%M:%S")
            except:
                formatted_time = "Unknown"

            file_info = {
                "success": True,
                "name": file_path.split("\\")[-1],
                "size": file_obj.get_filesize(),
                "created_time": formatted_time,
                "modified_time": formatted_time,
                "attributes": (
                    str(file_obj.get_attributes())
                    if hasattr(file_obj, "get_attributes")
                    else "Unknown"
                ),
                "is_directory": file_obj.is_directory(),
            }

            return file_info

        except Exception as e:
            return {"success": False, "error": f"获取文件信息失败: {str(e)}"}

    def disconnect(self):
        """断开连接"""
        try:
            if self.smb and self.connected:
                self.smb.close()
                self.connected = False
                logger.info("SMB连接已断开")
        except Exception as e:
            logger.error(f"断开连接时出错: {str(e)}")

        self.smb = None
        self.connected = False
        self.domain = None
        self.username = None
        self.password = None
        self.host = None
        self.address = None
        self.port = None
        self.lmhash = None
        self.nthash = None
        self.session = None
        self.smb_version = None
        self.current_share = None
        self.current_path = "\\"
