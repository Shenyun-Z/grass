# -*- coding: utf-8 -*-
"""pytest 根配置：把仓库根目录加入 sys.path，便于直接 import 项目模块"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
