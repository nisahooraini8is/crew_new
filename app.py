from flask import Flask, request, flash, render_template_string, render_template, jsonify, redirect, url_for, session, Response
from sqlalchemy import create_engine, Column, Integer, String, Text, Boolean, ForeignKey
from crewai import Agent, Task, Crew, Process
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import zipfile
import base64
from io import BytesIO
import os
from flask import session as flask_session
import sys
from io import StringIO 
import csv
from flask import make_response

app = Flask(__name__)
app.secret_key = "nisai8is1234"

db_uri = 'mysql+mysqlconnector://root:@localhost/newcrew'
# db_uri = 'mysql+mysqlconnector://hayat:Hayat_admin123@3.99.155.18/crew'
engine = create_engine(db_uri)
Session = sessionmaker(bind=engine)
Base = declarative_base()


class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    openai_api_key = Column(String(255), unique=True)

class Create_Agent(Base):
    __tablename__ = 'agents'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    role = Column(String(255), nullable=False)
    goal = Column(Text, nullable=False)
    verbose = Column(Boolean, nullable=False)
    backstory = Column(Text, nullable=False)
    allow_delegation = Column(Boolean, nullable=False)

class Create_Task(Base):
    __tablename__ = 'tasks'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    agent_id = Column(Integer, ForeignKey('agents.id'))
    task_name = Column(String(255), nullable=False)
    task_description = Column(Text, nullable=False)

class Execute_Task(Base):
    __tablename__ = 'execute_task'

    id = Column(Integer, primary_key=True)
    task_id = Column(Integer)
    user_id = Column(Integer, ForeignKey('users.id'))
    agent_id = Column(Integer, ForeignKey('agents.id'))
    task_name = Column(String(255), nullable=False)
    task_description = Column(Text, nullable=False)
    
Base.metadata.create_all(engine)

def create_session():
    return Session()

def fetch_agents(session):
    return session.query(Create_Agent).all()

def fetch_tasks(session):
    return session.query(Create_Task).all()



@app.route('/')
def index():
    agents = []
    tasks = []
    execute_task= []

    if 'user_id' in flask_session:
        user_id = flask_session['user_id']
        session = create_session()
        try:
            agents = session.query(Create_Agent).filter_by(user_id=user_id).all()
            tasks = session.query(Create_Task).filter_by(user_id=user_id).all()
            execute_task = session.query(Execute_Task).filter_by(user_id=user_id).all()
        except Exception as e:
            flash(f"Error: {e}")
        finally:
            session.close()

    return render_template('index.html', agents=agents, tasks=tasks,execute_task=execute_task)

@app.route('/clear_session', methods=['POST'])
def clear_session():
    if 'user_id' in session:
        user_id = session['user_id']
        session_data = create_session()
        execute_tasks = session_data.query(Execute_Task).filter_by(user_id=user_id).all()
        for task in execute_tasks:
            session_data.delete(task)
        session_data.commit()
        session.clear()  # Clear the session data after removing associated tasks
        return '', 204
    else:
        return jsonify({'error': 'User session not found.'}), 404

@app.route('/save_api_key', methods=['POST'])
def save_api_key():
        openai_api_key = request.form.get('api_key')
        db_session = create_session()


        try:
            user = db_session.query(User).filter_by(openai_api_key=openai_api_key).first()
            if user:
                flask_session['user_id'] = user.id  # Storing user ID in session
                flask_session['openai_api_key'] = openai_api_key  # Store API key in session
                flash('Login success!', 'success')
            else:
                new_user = User(openai_api_key=openai_api_key)
                db_session.add(new_user)
                db_session.commit()
                flask_session['user_id'] = new_user.id  # Storing new user ID in session
                flask_session['openai_api_key'] = openai_api_key  # Store API key in session
                flash('API Key set successfully!', 'success')
        except Exception as e:
            flash(f'Error: {str(e)}', 'error')
        finally:
            db_session.close()
        return redirect(url_for('index')) 

@app.route('/get_agent_tasks', methods=['GET'])
def get_agent_tasks():
    agent_id = request.args.get('agent_id')

    if agent_id is None:
        return jsonify({'error': 'Agent ID is required'}), 400

    session = create_session()
    try:
        # Assuming you have a relationship between Create_Agent and Create_Task models
        agent = session.query(Create_Agent).get(agent_id)
        if agent is None:
            return jsonify({'error': 'Agent not found'}), 404

        tasks = session.query(Create_Task).filter_by(agent_id=agent_id).all()

        # Convert tasks to a list of dictionaries
        tasks_list = [{'task_name': task.task_name, 'task_description': task.task_description} for task in tasks]

        return jsonify({'tasks': tasks_list})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()

@app.route('/create_agent', methods=['POST'])
def create_agent():
    if 'user_id' in flask_session:
        user_id = flask_session['user_id']
        role = request.form['role']
        goal = request.form['goal']
        verbose = request.form['verbose'] == 'yes'  # Adjusted comparison
        backstory = request.form['backstory']
        allow_delegation = request.form['allow_delegation'] == 'yes'  # Adjusted field name

        session = create_session()
        try:
            agent = Create_Agent(user_id=user_id, role=role, goal=goal, verbose=verbose, backstory=backstory, allow_delegation=allow_delegation)
            session.add(agent)
            session.commit()
            flash('Agent created successfully!', 'success')
        except Exception as e:
            flash(f'Error creating agent: {str(e)}', 'error')
            session.rollback()
        finally:
            session.close()
    else:
        flash('You must be logged in to create an agent.', 'error')

    return redirect(url_for('index'))

@app.route('/create_task', methods=['POST'])
def create_task():
    if 'user_id' in flask_session:
        user_id = flask_session['user_id']
        agent_id = request.form['selected_agent']
        task_name = request.form['task_name']
        task_description = request.form['task_description']

        session = create_session()
        try:
            task = Create_Task(user_id=user_id, agent_id=agent_id, task_name=task_name, task_description=task_description)
            session.add(task)
            session.commit()
            flash('Task added successfully!', 'success')
        except Exception as e:
            flash(f'Error adding task: {str(e)}', 'error')
            session.rollback()
        finally:
            session.close()
    else:
        flash('You must be logged in to create a task.', 'error')

    return redirect(url_for('index'))

@app.route('/addexecuteTask', methods=['POST'])
def execute_task():
    if 'user_id' in flask_session:
        user_id = flask_session['user_id']
        task_id = request.json.get('task_id')
        print(task_id,"taskis")
        session = create_session()
        try:
            # Retrieve the task from the database
            task = session.query(Create_Task).filter_by(id=task_id, user_id=user_id).first()
            if task:
                # Create an execution task
                execution_task = Execute_Task(
                    task_id=task.id,
                    user_id=user_id,
                    agent_id=task.agent_id,
                    task_name=task.task_name,
                    task_description=task.task_description
                )
                print(execution_task)
                session.add(execution_task)
                session.commit()
                flash('Task added for execution!', 'success')
            else:
                flash('Task not found or unauthorized.', 'error')
        except Exception as e:
            flash(f'Error executing task: {str(e)}', 'error')
            session.rollback()
        finally:
            session.close()
    else:
        flash('You must be logged in to added task.', 'error')

    return redirect(url_for('index'))


@app.route('/edelete_task', methods=['POST'])
def edelete_task():
    if 'user_id' in flask_session:
        task_id = request.form['task_id']
        session = create_session()
        try:
            task = session.query(Execute_Task).filter_by(id=task_id).first()
            if task:
                session.delete(task)
                session.commit()
                flash('Task removed successfully!', 'success')
            else:
                flash('Execute_Task not found.', 'error')
        except Exception as e:
            flash(f'Error deleting task: {str(e)}', 'error')
            session.rollback()
        finally:
            session.close()
    else:
        flash('You must be logged in to delete a task.', 'error')

    return redirect(url_for('index'))


@app.route('/delete_task', methods=['POST'])
def delete_task():
    if 'user_id' in flask_session:
        user_id = flask_session['user_id']
        task_id = request.form['task_id']
        session = create_session()
        try:
            # Check if the task exists in Create_Task table
            task_create = session.query(Create_Task).filter_by(id=task_id, user_id=user_id).first()
            if task_create:
                # Delete the task from the Create_Task table
                session.delete(task_create)

                # Check if the task exists in Execute_Task table for the same user and agent
                task_execute = session.query(Execute_Task).filter_by(task_id=task_id, user_id=user_id).first()
                if task_execute:
                    session.delete(task_execute)

                # Also, check if there are any other tasks with the same name and description in Execute_Task
                same_tasks = session.query(Execute_Task).filter_by(task_name=task_create.task_name, task_description=task_create.task_description, user_id=user_id, agent_id =task_create.agent_id).all()
                for same_task in same_tasks:
                    if same_task.id != task_id:  # Avoid deleting the same task again
                        session.delete(same_task)

                session.commit()
                flash('Task deleted successfully!', 'success')
            else:
                flash('Task not found.', 'error')
        except Exception as e:
            flash(f'Error deleting task: {str(e)}', 'error')
            session.rollback()
        finally:
            session.close()
    else:
        flash('You must be logged in to delete a task.', 'error')

    return redirect(url_for('index'))

@app.route('/reassign_task', methods=['POST'])
def reassign_task():
    if 'user_id' in flask_session:
        task_id = request.form['task_id']
        new_agent_id = request.form['new_agent_id']
        print(task_id,new_agent_id)

        session = create_session()
        try:
            task = session.query(Create_Task).filter_by(id=task_id).first()
            if task:
                # Create a new task with the same details but a different ID
                new_task = Create_Task(
                    user_id=task.user_id,
                    agent_id=new_agent_id,
                    task_name=task.task_name,
                    task_description=task.task_description
                )
                session.add(new_task)
                session.commit()

                flash('Task reassigned successfully!', 'success')
            else:
                flash('Task not found.', 'error')
        except Exception as e:
            flash(f'Error reassigning task: {str(e)}', 'error')
            session.rollback()
        finally:
            session.close()
    else:
        flash('You must be logged in to reassign a task.', 'error')

    return redirect(url_for('index'))


@app.route('/execute_tasks', methods=['POST'])
def execute_tasks():
    if 'user_id' in flask_session:
        agents = []
        tasks = []
        task_results = []  # Collect task results
        terminal_output = ""  # Initialize empty string to store terminal output

        user_id = flask_session['user_id']
        os.environ['OPENAI_API_KEY'] = flask_session.get('openai_api_key', '')
        openai_api_key = os.environ['OPENAI_API_KEY']

        session = create_session()
        data = request.get_json()
        task_order = data.get('task_order', [])
        output_option = data.get('output_option', 'Text')  # Default to 'Text' if not specified

        for task_id in task_order:
            task_agent_data = session.query(Execute_Task.task_description, Create_Agent.role, Create_Agent.goal, Create_Agent.verbose, Create_Agent.backstory, Create_Agent.allow_delegation).join(Create_Agent, Execute_Task.agent_id == Create_Agent.id).filter(Execute_Task.id == task_id, Execute_Task.user_id == user_id).first()
            
            if task_agent_data:
                agent = Agent(role=task_agent_data[1], goal=task_agent_data[2], verbose=True, backstory=task_agent_data[4], allow_delegation=task_agent_data[5], openai_api_key=openai_api_key)  # Ensured verbose is True for detailed logging
                task = Task(description=task_agent_data[0], agent=agent)
                agents.append(agent)
                tasks.append(task)

        if not tasks:
            flash('No tasks selected or tasks not found.', 'error')
            return redirect(url_for('index'))

        if tasks:
            app_dev_crew = Crew(api_key=openai_api_key, agents=agents, tasks=tasks,verbose=True, process=Process.sequential,share_crew=True,full_output=True)
            python_code = generate_python_code(agents, tasks)
            for task in tasks:
                # Redirecting stdout to capture terminal output
                captured_output = StringIO()
                sys.stdout = captured_output

                # Execute task
                result = app_dev_crew.kickoff()

                # Resetting stdout to original value
                sys.stdout = sys.__stdout__

                # Appending captured output to terminal_output
                terminal_output += captured_output.getvalue() + "\n"

                # Store result for this task
                task_results.append(result)

        all_results = "\n".join(task_results)  # Concatenate results

        # Create ZIP file in memory
        in_memory_zip = BytesIO()
        with zipfile.ZipFile(in_memory_zip, mode="w", compression=zipfile.ZIP_DEFLATED) as zipf:
            zipf.writestr('task_results.txt', f"All Task Results:\n{all_results}")
            zipf.writestr('generated_script.py', python_code)
            zipf.writestr('Verbose_output.txt', terminal_output)
        
        in_memory_zip.seek(0)
        encoded_zip = base64.b64encode(in_memory_zip.read()).decode('utf-8')

        return jsonify({'result': all_results, 'encoded_zip': encoded_zip, 'output_option': output_option})
    else:
        # Handle case where user_id is not in session
        return jsonify({'error': 'User not logged in'}), 401

def generate_python_code(agents, tasks):
    code = "from crewai import Agent, Task, Crew, Process\nimport os\n\n"
    code += f'os.environ["OPENAI_API_KEY"] = "{os.getenv("OPENAI_API_KEY")}"\n\n'
    
    agent_vars = []  # To keep track of agent variable names
    task_vars = []  # To keep track of task variable names
    
    # Generating Agent instances
    for i, agent in enumerate(agents, start=1):
        var_name = f'{agent.role.lower().replace(" ", "_")}_{i}'
        agent_vars.append(var_name)
        code += f'{var_name} = Agent(\n'
        code += f'  role="{agent.role}",\n'
        code += f'  goal="{agent.goal}",\n'
        code += f'  verbose={agent.verbose},\n'
        code += f'  backstory="{agent.backstory}",\n'
        code += f'  allow_delegation={agent.allow_delegation}\n'
        code += ')\n\n'
    
    # Generating Task instances and associating them with agents
    for i, task in enumerate(tasks, start=1):
        agent_var_name = task.agent.role.lower().replace(" ", "_") + "_" + str(i)  # Assuming task.agent gives the associated agent
        task_var_name = f'task_{i}'
        task_vars.append(task_var_name)
        code += f'{task_var_name} = Task(\n'
        code += f'    description="{task.description}",\n'
        code += f'    agent={agent_var_name}\n'
        code += ')\n\n'
    
    # Adding the Crew instantiation with dynamically accumulated agents and tasks
    code += "# Instantiate your Crew with agents and tasks\n"
    code += "app_dev_crew = Crew(\n"
    code += "    agents=[" + ", ".join(agent_vars) + "],\n"
    code += "    tasks=[" + ", ".join(task_vars) + "],\n"
    code += "    process=Process.sequential  # The tasks will be executed in a sequential manner.\n"
    code += ")\n"
    code += "result = app_dev_crew.kickoff()\n"
    return code


def consolidate_code():
    with open(__file__, 'r') as file:
        code_content = file.read()
    return code_content


@app.route('/export_agents')
def export_agents():
    if 'user_id' not in flask_session:
        flash('You must be logged in to export agents.', 'error')
        return redirect(url_for('index'))

    user_id = flask_session['user_id']
    session = create_session()
    agents = session.query(Create_Agent).filter_by(user_id=user_id).all()
    session.close()

    # Creating a CSV in memory
    si = StringIO()
    cw = csv.writer(si)
    cw.writerow(['Role', 'Goal', 'Verbose', 'Backstory', 'Allow Delegation'])  # Header row
    for agent in agents:
        cw.writerow([agent.role, agent.goal, agent.verbose, agent.backstory, agent.allow_delegation])

    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = "attachment; filename=agents.csv"
    output.headers["Content-type"] = "text/csv"
    return output

@app.route('/import_agents', methods=['POST'])
def import_agents():
    if 'user_id' not in flask_session:
        flash('You must be logged in to import agents.', 'error')
        return redirect(url_for('index'))

    file = request.files.get('file')
    if not file:
        flash('No file selected.', 'error')
        return redirect(url_for('index'))

    user_id = flask_session['user_id']
    session = create_session()      
    try:
        csv_file = csv.reader(file.read().decode('utf-8').splitlines())
        next(csv_file, None)  # Skip header row
        for row in csv_file:
            print(row)
            print(row[0])

            verbose = True if row[2].lower() == 'true' else False
            allow_delegation = True if row[4].lower() == 'true' else False
            try:
                agent = Create_Agent(
                             user_id=user_id,
                                role=row[0],
                                goal=row[1],
                                verbose=verbose,  # Converted from string to Boolean
                                backstory=row[3],
                                allow_delegation=allow_delegation  # Converted from string to Boolean
                            )                
                session.add(agent)
                session.commit()
                flash('Agent created successfully!', 'success')
            except Exception as e:
                flash(f'Error creating agent: {str(e)}', 'error')
        flash('Agents imported successfully!', 'success')
    except Exception as e:
        session.rollback()
        flash(f'Error importing agents: {str(e)}', 'error')
    finally:
        session.close()

    return redirect(url_for('index'))

if __name__ == "__main__":
    
    app.run(host='0.0.0.0',port=2010)
