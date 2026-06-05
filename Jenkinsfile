pipeline {
    agent any

    parameters {
        choice(name: 'ENVIRONMENT', choices: ['dev', 'staging', 'production'], description: '测试环境')
        string(name: 'TAGS', defaultValue: 'smoke', description: '用例标签')
        string(name: 'WORKERS', defaultValue: '4', description: '并发数')
    }

    environment {
        ENV = "${params.ENVIRONMENT}"
        DB_PASSWORD = credentials('db-password')
        API_KEY = credentials('api-key')
    }

    stages {
        stage('Setup') {
            steps {
                sh 'pip install -r requirements.txt'
            }
        }

        stage('Test') {
            steps {
                sh """
                    pytest --env=${ENV} \
                           -m "${TAGS}" \
                           -n ${WORKERS} \
                           --alluredir=reports/allure-results \
                           -v
                """
            }
        }
    }

    post {
        always {
            allure([
                results: [[path: 'reports/allure-results']],
                reportBuildPolicy: 'ALWAYS'
            ])
            cleanWs()
        }
        failure {
            emailext(
                subject: "API 测试失败 - ${ENV}",
                body: "详见 Allure 报告: ${BUILD_URL}allure",
                to: '${DEFAULT_RECIPIENTS}'
            )
        }
    }
}
