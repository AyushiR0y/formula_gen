from flask import Blueprint, jsonify, request
from models import Task, Session
from backend.llm_utils import process_with_llm

api = Blueprint('api', __name__)

@api.route('/tasks', methods=['GET'])
def get_tasks():
    session = Session()
    tasks = session.query(Task).all()
    return jsonify([{'id': t.id, 'title': t.title, 'desc': t.description} for t in tasks])

@api.route('/tasks', methods=['POST'])
def create_task():
    data = request.json
    session = Session()
    new_task = Task(title=data['title'], description=data['description'])
    session.add(new_task)
    session.commit()
    return jsonify({'message': 'Task created'}), 201

@api.route('/tasks/llm', methods=['POST'])
def analyze_task():
    data = request.json
    result = process_with_llm(data['input'])
    return jsonify({'llm_response': result})
