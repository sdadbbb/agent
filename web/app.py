"""Flask 应用入口"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _get_base_dir():
    """获取项目根目录（兼容 PyInstaller 打包）"""
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


from flask import Flask, render_template

from web.routes_agent import agent_bp
from web.routes_cases import cases_bp
from web.routes_files import files_bp
from web.routes_reports import reports_bp


def create_app():
    base = _get_base_dir()
    app = Flask(__name__,
                template_folder=os.path.join(base, 'templates'),
                static_folder=os.path.join(base, 'static'))

    # 注册蓝图
    app.register_blueprint(agent_bp)
    app.register_blueprint(cases_bp)
    app.register_blueprint(files_bp)
    app.register_blueprint(reports_bp)

    # 页面路由
    @app.route('/')
    def index():
        return render_template('index.html')

    @app.route('/cases')
    def cases_page():
        return render_template('cases.html')

    @app.route('/reports')
    def reports_page():
        return render_template('reports.html')

    @app.route('/api/shutdown', methods=['POST'])
    def shutdown():
        """关闭服务（桌面应用专用）"""
        import os as _os
        _os._exit(0)

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=5000, debug=True)
