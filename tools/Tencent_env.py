#!/usr/bin/env python3
import os
import sys
import configparser
from pathlib import Path

# 腾讯云常用环境变量列表
TENCENT_ENV_VARS = {
    "TENCENTCLOUD_SECRET_ID": "腾讯云API密钥ID",
    "TENCENTCLOUD_SECRET_KEY": "腾讯云API密钥Key",
    "TENCENTCLOUD_REGION": "默认地域（如ap-beijing、ap-guangzhou）"
}

def load_config(config_path):
    """从配置文件加载环境变量"""
    if not os.path.exists(config_path):
        return None
    
    config = configparser.ConfigParser()
    try:
        config.read(config_path)
        if "tencentcloud" in config.sections():
            return dict(config["tencentcloud"])
    except Exception as e:
        print(f"加载配置文件失败: {e}", file=sys.stderr)
    return None

def save_config(config_path, env_vars):
    """保存环境变量到配置文件"""
    config = configparser.ConfigParser()
    config["tencentcloud"] = env_vars
    
    try:
        with open(config_path, "w") as f:
            config.write(f)
        print(f"配置已保存到 {config_path}")
    except Exception as e:
        print(f"保存配置文件失败: {e}", file=sys.stderr)

def set_env_vars(env_vars, persist=False):
    """设置环境变量，支持临时设置和持久化"""
    # 临时设置（当前进程有效）
    for key, value in env_vars.items():
        os.environ[key] = value
        print(f"已设置 {key} = ******{value[-4:]}")  # 隐藏部分字符
    
    if not persist:
        return
    
    # 持久化设置（根据系统写入配置文件）
    if sys.platform.startswith("win"):
        # Windows系统（需要管理员权限）
        for key, value in env_vars.items():
            os.system(f'setx {key} "{value}" >nul 2>&1')
        print("持久化设置已完成（需重启终端生效）")
    else:
        # Linux/Mac系统（写入bashrc或zshrc）
        shell_config = Path.home() / (".zshrc" if os.path.exists(Path.home() / ".zshrc") else ".bashrc")
        with open(shell_config, "a") as f:
            f.write("\n# 腾讯云环境变量\n")
            for key, value in env_vars.items():
                f.write(f'export {key}="{value}"\n')
        print(f"持久化设置已写入 {shell_config}（需执行 source {shell_config} 生效）")

def main():
    print("=== 腾讯云环境变量快速设置工具 ===")
    
    # 检查是否有配置文件
    config_path = Path.home() / ".tencentcloud.ini"
    config = load_config(config_path)
    
    if config:
        use_config = input(f"检测到配置文件 {config_path}，是否使用? [y/n] ").lower() == "y"
        if use_config:
            env_vars = config
        else:
            env_vars = {}
    else:
        env_vars = {}
    
    # 交互式输入缺失的环境变量
    for key, desc in TENCENT_ENV_VARS.items():
        if key not in env_vars or not env_vars[key]:
            env_vars[key] = input(f"请输入{desc}：").strip()
            while not env_vars[key]:
                env_vars[key] = input(f"{desc}不能为空，请重新输入：").strip()
    
    # 询问是否持久化
    persist = input("是否将设置持久化到系统环境变量? [y/n] ").lower() == "y"
    if persist:
        save_config(config_path, env_vars)
    
    # 应用设置
    set_env_vars(env_vars, persist)
    print("=== 环境变量设置完成 ===")

if __name__ == "__main__":
    main()