pipeline { 
    agent any 
    environment { 
       PROJECT_ROOT = "$WORKSPACE"
       PUP_SCRIPTS = "$WORKSPACE/scripts"
       PUP_PYTHON = "$WORKSPACE/scripts/python"
       PUP_VENV = "$WORKSPACE/pup-venv"
       PYTHON_ACTIVATE = "$WORKSPACE/pup-venv/bin/activate"
       JENKINS_DIR = "$WORKSPACE/Jenkins"
    } 
    stages { 
        stage('Setup Environment') { 
            steps { 
                echo 'Running Workspace setup ...' 
                sh "bash $JENKINS_DIR/setup_workspace.sh" 
            } 
        } 
        stage('Run Tests') { 
            steps { 
                echo 'Testing ...' 
                sh "$JENKINS_DIR/run_test.sh" 
            } 
        } 
    }
}
