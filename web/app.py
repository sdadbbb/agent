"""Flask 应用入口"""
import os
import sys
from flask import Flask, render_template

# 添加项目根目录到 path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from web.routes_agent import agent_bp
from web.routes_cases import cases_bp
from web.routes_files import files_bp
from web.routes_reports import reports_bp


def create_app():
    app = Flask(__name__,
                template_folder=os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'templates'),
                static_folder=os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'static'))

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

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=5000, debug=True)
