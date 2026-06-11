import numpy as np
from OpenGL.GL import *


VERTEX_SHADER = """
#version 330 core

layout (location = 0) in vec3 aPos;
layout (location = 1) in vec2 aTexCoord;
layout (location = 2) in vec3 aNormal;

uniform mat4 model;
uniform mat4 view;
uniform mat4 projection;

out vec2 TexCoord;
out vec3 FragPos;
out vec3 Normal;

void main()
{
    vec4 worldPos = model * vec4(aPos, 1.0);
    gl_Position = projection * view * worldPos;
    FragPos = worldPos.xyz;
    Normal = mat3(transpose(inverse(model))) * aNormal;
    TexCoord = aTexCoord;
}
"""


FRAGMENT_SHADER = """
#version 330 core

in vec2 TexCoord;
in vec3 FragPos;
in vec3 Normal;
out vec4 FragColor;

struct Light {
    vec3 position;
    vec3 color;
    int enabled;
    int environment;
};

#define MAX_LIGHTS 4

uniform sampler2D texture1;
uniform int useTexture;
uniform vec3 tint;
uniform vec3 viewPos;
uniform Light lights[MAX_LIGHTS];
uniform int objectEnvironment;
uniform int ambientEnabled;
uniform float ambientStrength;
uniform float diffuseReflection;
uniform float specularReflection;
uniform float shininess;
uniform int emissive;
uniform vec3 emissiveColor;

void main()
{
    vec4 baseColor;

    if (useTexture == 1)
        baseColor = texture(texture1, TexCoord) * vec4(tint, 1.0);
    else
        baseColor = vec4(tint, 1.0);

    if (emissive == 1) {
        FragColor = vec4(baseColor.rgb * emissiveColor, baseColor.a);
        return;
    }

    vec3 norm = normalize(Normal);
    vec3 viewDir = normalize(viewPos - FragPos);

    vec3 result = vec3(0.0);

    if (ambientEnabled == 1)
        result += ambientStrength * baseColor.rgb;

    for (int i = 0; i < MAX_LIGHTS; i++) {
        if (lights[i].enabled == 0 || lights[i].environment != objectEnvironment)
            continue;

        vec3 lightDir = normalize(lights[i].position - FragPos);
        float distance = length(lights[i].position - FragPos);
        float attenuation = 1.0 / (1.0 + 0.045 * distance + 0.0075 * distance * distance);

        float diff = max(dot(norm, lightDir), 0.0);
        vec3 diffuse = diffuseReflection * diff * lights[i].color * baseColor.rgb;

        vec3 reflectDir = reflect(-lightDir, norm);
        float spec = pow(max(dot(viewDir, reflectDir), 0.0), shininess);
        vec3 specular = specularReflection * spec * lights[i].color;

        result += attenuation * (diffuse + specular);
    }

    FragColor = vec4(result, baseColor.a);
}
"""


SKYBOX_VERTEX_SHADER = """
#version 330 core

layout (location = 0) in vec3 aPos;

out vec3 TexCoords;

uniform mat4 view;
uniform mat4 projection;

void main()
{
    TexCoords = aPos;
    vec4 pos = projection * view * vec4(aPos, 1.0);
    gl_Position = pos.xyww;
}
"""


SKYBOX_FRAGMENT_SHADER = """
#version 330 core

in vec3 TexCoords;
out vec4 FragColor;

uniform samplerCube skybox;

void main()
{
    FragColor = texture(skybox, TexCoords);
}
"""


def compile_shader(source: str, shader_type: int) -> int:
    shader = glCreateShader(shader_type)
    glShaderSource(shader, source)
    glCompileShader(shader)

    if not glGetShaderiv(shader, GL_COMPILE_STATUS):
        error = glGetShaderInfoLog(shader).decode("utf-8", errors="replace")
        raise RuntimeError(error)

    return shader


def create_program(vertex_source: str, fragment_source: str) -> int:
    vertex = compile_shader(vertex_source, GL_VERTEX_SHADER)
    fragment = compile_shader(fragment_source, GL_FRAGMENT_SHADER)

    program = glCreateProgram()
    glAttachShader(program, vertex)
    glAttachShader(program, fragment)
    glLinkProgram(program)

    if not glGetProgramiv(program, GL_LINK_STATUS):
        error = glGetProgramInfoLog(program).decode("utf-8", errors="replace")
        raise RuntimeError(error)

    glDeleteShader(vertex)
    glDeleteShader(fragment)

    return program


def set_int(program: int, name: str, value: int) -> None:
    glUniform1i(glGetUniformLocation(program, name), value)


def set_float(program: int, name: str, value: float) -> None:
    glUniform1f(glGetUniformLocation(program, name), value)


def set_vec3(program: int, name: str, value: tuple[float, float, float]) -> None:
    glUniform3f(glGetUniformLocation(program, name), value[0], value[1], value[2])


def set_mat4(program: int, name: str, matrix: np.ndarray) -> None:
    glUniformMatrix4fv(
        glGetUniformLocation(program, name),
        1,
        GL_TRUE,
        matrix.astype(np.float32),
    )
