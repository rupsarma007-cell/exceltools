from flask import Flask, Blueprint

app = Flask(__name__)

test_bp = Blueprint('test', __name__)
@test_bp.route('/')
def test():
    return "Blueprint works!"

app.register_blueprint(test_bp, url_prefix='/test')

if __name__ == '__main__':
    app.run(port=5001)