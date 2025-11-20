#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SMB Client GUI - PyWebView桌面应用
基于Python+PyWebView的SMB客户端GUI应用
"""

import webview
import threading
import json
import os
import sys
import logging
from pathlib import Path

# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from smb_handler import SMBHandler

# 配置日志
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class SMBApi:
    """API类，处理前端的JavaScript调用"""

    def __init__(self):
        self.smb_handler = None

    def connect(self, connection_string):
        """使用连接字符串连接SMB服务器"""
        try:
            logger.info("🎯 [后端API] connect 函数被调用")
            logger.info(f"🎯 [后端API] 连接字符串: {connection_string}")
            logger.info("🎯 [后端API] 开始创建SMBHandler实例")

            if not connection_string:
                return {"success": False, "error": "连接字符串不能为空"}

            # 创建SMB处理器
            logger.info("🎯 [后端API] 创建SMBHandler实例")
            self.smb_handler = SMBHandler()

            # 尝试连接
            logger.info("🎯 [后端API] 调用smb_handler.connect")
            result = self.smb_handler.connect(connection_string)
            logger.info(f"🎯 [后端API] smb_handler.connect 返回: {result}")

            if result["success"]:
                logger.info("🎯 [后端API] 连接成功")
                return {"success": True, "message": "连接成功"}
            else:
                logger.error(f"🎯 [后端API] 连接失败: {result['error']}")
                self.smb_handler = None
                return {"success": False, "error": result["error"]}

        except Exception as e:
            logger.error(f"连接错误: {str(e)}")
            self.smb_handler = None
            return {"success": False, "error": str(e)}

    def list_files(self, path="\\"):
        """列出文件和目录"""
        try:
            logger.info("📁 [后端API] list_files 函数被调用")
            logger.info(f"📁 [后端API] 参数: path={path}")

            if not self.smb_handler:
                logger.error("📁 [后端API] 未连接到SMB服务器")
                return {"success": False, "error": "未连接到SMB服务器"}

            logger.info("📁 [后端API] 调用smb_handler.list_directory")
            result = self.smb_handler.list_directory(path)
            logger.info(f"📁 [后端API] smb_handler.list_directory 返回: {result}")

            if result["success"]:
                return {"success": True, "files": result["files"]}
            else:
                return {"success": False, "error": result["error"]}

        except Exception as e:
            logger.error(f"列出文件错误: {str(e)}")
            return {"success": False, "error": str(e)}

    def download_file(
        self, share_name, file_path, local_path=None, save_to_download=False
    ):
        """下载文件"""
        try:
            logger.info("⬇️ [后端API] download_file 函数被调用")
            logger.info(
                f"⬇️ [后端API] 参数: share_name={share_name}, file_path={file_path}, local_path={local_path}, save_to_download={save_to_download}"
            )

            if not self.smb_handler:
                logger.error("⬇️ [后端API] 未连接到SMB服务器")
                return {"success": False, "error": "未连接到SMB服务器"}

            # 如果要求保存到download目录
            if save_to_download:
                import os
                from pathlib import Path

                # 创建download目录
                download_dir = Path(__file__).parent / "download"
                download_dir.mkdir(exist_ok=True)

                # 获取文件名
                file_name = os.path.basename(file_path)
                local_path = download_dir / file_name

                logger.info(f"⬇️ [后端API] 保存到download目录: {local_path}")

            logger.info("⬇️ [后端API] 调用smb_handler.download_file")
            result = self.smb_handler.download_file(
                share_name, file_path, str(local_path) if local_path else None
            )
            logger.info(f"⬇️ [后端API] smb_handler.download_file 返回 (原始): {result}")

            # 如果是保存到本地文件，返回成功信息
            if save_to_download and result.get("success"):
                result["local_path"] = str(local_path)
                result["message"] = f"文件已保存到: {local_path}"
                return result

            # 如果返回了数据并且不是本地文件保存，需要转换为Base64以便JSON序列化
            if (
                result.get("success")
                and "data" in result
                and isinstance(result["data"], bytes)
            ):
                import base64

                logger.info("⬇️ [后端API] 检测到bytes数据，转换为Base64以便JSON序列化")
                data_base64 = base64.b64encode(result["data"]).decode("utf-8")
                result["data"] = data_base64
                logger.info(
                    f"⬇️ [后端API] Base64转换完成，原始大小: {len(result['data'])} bytes"
                )

            logger.info(f"⬇️ [后端API] 最终返回给前端: {result}")
            return result

        except Exception as e:
            logger.error(f"下载文件错误: {str(e)}")
            return {"success": False, "error": str(e)}

    def upload_file(self, share_name, file_path, file_data):
        """上传文件"""
        try:
            logger.info("⬆️ [后端API] upload_file 函数被调用")
            logger.info(
                f"⬆️ [后端API] 参数: share_name={share_name}, file_path={file_path}, file_data类型={type(file_data)}"
            )

            if not self.smb_handler:
                logger.error("⬆️ [后端API] 未连接到SMB服务器")
                return {"success": False, "error": "未连接到SMB服务器"}

            # 检查文件数据类型并转换
            if isinstance(file_data, str):
                # 如果是Base64字符串，转换回bytes
                import base64

                logger.info("⬆️ [后端API] 检测到Base64字符串，正在转换为bytes")
                file_data = base64.b64decode(file_data)
                logger.info(f"⬆️ [后端API] Base64转换完成，bytes大小: {len(file_data)}")
            elif not isinstance(file_data, bytes):
                error_msg = (
                    f"不支持的文件数据类型: {type(file_data)}，期望bytes或Base64字符串"
                )
                logger.error(f"⬆️ [后端API] {error_msg}")
                return {"success": False, "error": error_msg}

            logger.info("⬆️ [后端API] 调用smb_handler.upload_file")
            result = self.smb_handler.upload_file(share_name, file_path, file_data)
            logger.info(f"⬆️ [后端API] smb_handler.upload_file 返回: {result}")

            return result

        except Exception as e:
            logger.error(f"上传文件错误: {str(e)}")
            return {"success": False, "error": str(e)}

    def get_file_info(self, share_name, file_path):
        """获取文件信息"""
        try:
            logger.info("ℹ️ [后端API] get_file_info 函数被调用")
            logger.info(
                f"ℹ️ [后端API] 参数: share_name={share_name}, file_path={file_path}"
            )

            if not self.smb_handler:
                logger.error("ℹ️ [后端API] 未连接到SMB服务器")
                return {"success": False, "error": "未连接到SMB服务器"}

            logger.info("ℹ️ [后端API] 调用smb_handler.get_file_info")
            result = self.smb_handler.get_file_info(share_name, file_path)
            logger.info(f"ℹ️ [后端API] smb_handler.get_file_info 返回: {result}")

            return result

        except Exception as e:
            logger.error(f"获取文件信息错误: {str(e)}")
            return {"success": False, "error": str(e)}

    def disconnect(self):
        """断开SMB连接"""
        try:
            logger.info("🔌 [后端API] disconnect 函数被调用")
            logger.info("🔌 [后端API] 开始断开连接")

            if self.smb_handler:
                logger.info("🔌 [后端API] 调用smb_handler.disconnect")
                self.smb_handler.disconnect()
                self.smb_handler = None
                logger.info("🔌 [后端API] SMB连接已断开")
            else:
                logger.info("🔌 [后端API] 没有活跃的连接需要断开")

            logger.info("🔌 [后端API] 断开连接成功")
            return {"success": True, "message": "连接已断开"}
        except Exception as e:
            logger.error(f"断开连接错误: {str(e)}")
            return {"success": False, "error": str(e)}


def get_html_content(template_file):
    """获取HTML模板内容"""
    try:
        template_path = Path(__file__).parent / "templates" / template_file
        if template_path.exists():
            with open(template_path, "r", encoding="utf-8") as f:
                content = f.read()
                # 修复相对路径引用
                content = content.replace(
                    'href="/static/',
                    'href="file:///'
                    + str(Path(__file__).parent / "static").replace("\\", "/")
                    + "/",
                )
                content = content.replace(
                    'src="/static/',
                    'src="file:///'
                    + str(Path(__file__).parent / "static").replace("\\", "/")
                    + "/",
                )
                return content
        else:
            return f"<h1>错误: 找不到模板文件 {template_file}</h1>"
    except Exception as e:
        return f"<h1>错误加载模板: {str(e)}</h1>"


def get_static_content(static_file):
    """获取静态文件内容"""
    try:
        file_path = Path(__file__).parent / "static" / static_file
        if file_path.exists():
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
        else:
            return f"/* 找不到文件 {static_file} */"
    except Exception as e:
        return f"/* 错误加载文件: {str(e)} */"


def main():
    """主函数"""
    print("SMB Client GUI 正在启动...")
    print("=" * 50)

    # 检查依赖
    try:
        import webview
        from impacket import smbconnection

        print("[OK] 依赖检查通过")
    except ImportError as e:
        print(f"[ERROR] 缺少依赖: {e}")
        print("请运行: pip install -r requirements.txt")
        sys.exit(1)

    # 创建API实例
    api = SMBApi()

    # 创建WebView窗口
    window = webview.create_window(
        "SMB Client GUI",
        html=get_html_content("main.html"),
        js_api=api,
        width=1200,
        height=950,
        resizable=True,
    )

    print("[OK] 窗口已创建")
    print("[INFO] 正在加载页面...")

    # 启动应用
    try:
        # 开启debug模式以便调试
        # PyWebView会在页面加载完成后自动让前端JavaScript运行
        # 前端的waitForPyWebView()函数会检测API何时可用
        webview.start(debug=True)
    except Exception as e:
        print(f"[ERROR] 启动失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
