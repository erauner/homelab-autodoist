def IMAGE_NAME = 'autodoist'
def REGISTRY = 'docker.nexus.erauner.dev'

// Inline kaniko pod template
def kanikoPodTemplate = '''
apiVersion: v1
kind: Pod
metadata:
  labels:
    workload-type: ci-builds
spec:
  imagePullSecrets:
  - name: nexus-registry-credentials
  containers:
  - name: jnlp
    image: jenkins/inbound-agent:3355.v388858a_47b_33-3-jdk21
    resources:
      requests:
        cpu: 100m
        memory: 256Mi
      limits:
        cpu: 500m
        memory: 512Mi
  - name: kaniko
    image: gcr.io/kaniko-project/executor:debug
    command: ['sleep', '3600']
    volumeMounts:
    - name: nexus-creds
      mountPath: /kaniko/.docker
    resources:
      requests:
        cpu: 500m
        memory: 1Gi
      limits:
        cpu: 1000m
        memory: 2Gi
  volumes:
  - name: nexus-creds
    secret:
      secretName: nexus-registry-credentials
'''

pipeline {
    agent {
        kubernetes {
            yaml kanikoPodTemplate
        }
    }

    options {
        buildDiscarder(logRotator(numToKeepStr: '10'))
        timeout(time: 15, unit: 'MINUTES')
    }

    environment {
        DOCKER_CONFIG = '/kaniko/.docker'
    }

    stages {
        stage('Build & Push') {
            when {
                anyOf {
                    branch 'master'
                    branch 'main'
                }
            }
            steps {
                container('kaniko') {
                    script {
                        def shortCommit = sh(script: 'echo $GIT_COMMIT | cut -c1-7', returnStdout: true).trim()
                        def destinations = "--destination=${REGISTRY}/${IMAGE_NAME}:${shortCommit} --destination=${REGISTRY}/${IMAGE_NAME}:latest"

                        sh """
                            /kaniko/executor \
                                --context=\${WORKSPACE} \
                                --dockerfile=\${WORKSPACE}/Dockerfile \
                                ${destinations} \
                                --cache=true \
                                --cache-repo=${REGISTRY}/${IMAGE_NAME}-cache
                        """
                    }
                }
            }
        }
    }

    post {
        success {
            script {
                if (env.BRANCH_NAME == 'master' || env.BRANCH_NAME == 'main') {
                    def shortCommit = sh(script: 'echo $GIT_COMMIT | cut -c1-7', returnStdout: true).trim()
                    echo "✅ Image pushed: ${REGISTRY}/${IMAGE_NAME}:${shortCommit}"
                }
            }
        }
        failure {
            echo '❌ Build failed'
        }
    }
}
