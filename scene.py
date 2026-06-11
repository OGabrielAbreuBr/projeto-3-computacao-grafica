from dataclasses import dataclass
from typing import Optional

from config import (
    HOUSE_FLOOR_TEXTURE,
    HOUSE_OBJ,
    MODELS_DIR,
    GRASS_TEXTURE,
)
from matrices import model_matrix
from shaders import set_float, set_int, set_mat4, set_vec3
from mesh import create_colored_cube, create_plane
from obj_loader import load_obj, fit_obj_on_ground, fit_small_obj_on_ground


ENV_INTERNAL = 0
ENV_EXTERNAL = 1


@dataclass
class SceneObject:
    name: str
    mesh: object
    position: tuple[float, float, float]
    rotation: tuple[float, float, float]
    scale: tuple[float, float, float]
    environment: int
    diffuse_reflection: float = 0.75
    specular_reflection: float = 0.35
    shininess: float = 32.0
    emissive: bool = False
    emissive_color: tuple[float, float, float] = (1.0, 1.0, 1.0)
    follow_object: Optional["SceneObject"] = None
    follow_offset: tuple[float, float, float] = (0.0, 0.0, 0.0)

    def draw(self, program: int) -> None:
        position = self.position

        if self.follow_object is not None:
            x, y, z = self.follow_object.position
            ox, oy, oz = self.follow_offset
            position = (x + ox, y + oy, z + oz)

        m = model_matrix(position, self.rotation, self.scale)
        set_mat4(program, "model", m)
        set_int(program, "objectEnvironment", self.environment)
        set_float(program, "diffuseReflection", self.diffuse_reflection)
        set_float(program, "specularReflection", self.specular_reflection)
        set_float(program, "shininess", self.shininess)
        set_int(program, "emissive", 1 if self.emissive else 0)
        set_vec3(program, "emissiveColor", self.emissive_color)
        self.mesh.draw(program)


@dataclass
class LightSource:
    name: str
    position: tuple[float, float, float]
    color: tuple[float, float, float]
    environment: int
    enabled: bool = True
    marker_object: Optional[SceneObject] = None
    attached_object: Optional[SceneObject] = None
    offset: tuple[float, float, float] = (0.0, 0.0, 0.0)

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = enabled

        if self.marker_object is not None:
            self.marker_object.emissive = enabled
            self.marker_object.emissive_color = self.color if enabled else (0.12, 0.12, 0.12)

    def current_position(self) -> tuple[float, float, float]:
        if self.attached_object is None:
            return self.position

        x, y, z = self.attached_object.position
        ox, oy, oz = self.offset
        return (x + ox, y + oy, z + oz)


@dataclass
class LightingState:
    ambient_enabled: bool = True
    ambient_strength: float = 0.18
    lights: Optional[list[LightSource]] = None

    def __post_init__(self) -> None:
        if self.lights is None:
            self.lights = []

    def apply(self, program: int) -> None:
        set_int(program, "ambientEnabled", 1 if self.ambient_enabled else 0)
        set_float(program, "ambientStrength", self.ambient_strength)

        for index, light in enumerate(self.lights):
            prefix = f"lights[{index}]"
            set_vec3(program, f"{prefix}.position", light.current_position())
            set_vec3(program, f"{prefix}.color", light.color)
            set_int(program, f"{prefix}.enabled", 1 if light.enabled else 0)
            set_int(program, f"{prefix}.environment", light.environment)


@dataclass
class SceneControls:
    translating_object: Optional[SceneObject] = None
    lighting: Optional[LightingState] = None


def add_model_object(
    objects: list[SceneObject],
    name: str,
    filename: str,
    target_size: float,
    target_center: tuple[float, float, float],
    rotation: tuple[float, float, float],
    environment: int,
    diffuse_reflection: float = 0.75,
    specular_reflection: float = 0.35,
    shininess: float = 32.0,
    optional: bool = True,
) -> Optional[SceneObject]:
    obj_path = MODELS_DIR / filename

    if not obj_path.exists():
        msg = f"[AVISO] Modelo não encontrado: {obj_path}"

        if optional:
            print(msg)
            return None

        raise FileNotFoundError(msg)

    model = load_obj(obj_path)

    position, scale = fit_small_obj_on_ground(
        obj_path=obj_path,
        target_size=target_size,
        target_center=target_center,
        rotation_y_degrees=rotation[1],
    )

    scene_object = SceneObject(
        name=name,
        mesh=model,
        position=position,
        rotation=rotation,
        scale=scale,
        environment=environment,
        diffuse_reflection=diffuse_reflection,
        specular_reflection=specular_reflection,
        shininess=shininess,
    )

    objects.append(scene_object)

    return scene_object


def build_scene() -> tuple[list[SceneObject], SceneControls]:
    objects: list[SceneObject] = []
    controls = SceneControls()

    if not HOUSE_OBJ.exists():
        raise FileNotFoundError(
            f"Não encontrei a casa: {HOUSE_OBJ}\n\n"
            "Coloque os arquivos assim:\n"
            "  casa/Cottage_FREE.obj\n"
            "  casa/Cottage_FREE.mtl\n"
            "  casa/Cottage_Clean/texturas...\n"
        )

    # -------------------------------------------------------------------------
    # Casa
    # -------------------------------------------------------------------------
    house_model = load_obj(HOUSE_OBJ)

    house_rotation_y = 0.0

    house_position, house_scale = fit_obj_on_ground(
        HOUSE_OBJ,
        target_width=26.0,
        target_center=(0.0, 0.0, 0.0),
        rotation_y_degrees=house_rotation_y,
    )

    objects.append(SceneObject(
        name="cottage",
        mesh=house_model,
        position=house_position,
        rotation=(0.0, house_rotation_y, 0.0),
        scale=house_scale,
        environment=ENV_EXTERNAL,
        diffuse_reflection=0.65,
        specular_reflection=0.12,
        shininess=18.0,
    ))

    # -------------------------------------------------------------------------
    # Piso interno da casa
    # -------------------------------------------------------------------------
    house_floor_mesh = create_plane(
        width=20.0,
        depth=18.65,
        uv_repeat=8.0,
        texture_path=HOUSE_FLOOR_TEXTURE,
    )

    objects.append(SceneObject(
        name="piso_interno_casa",
        mesh=house_floor_mesh,
        position=(0.0, 0.08, -1.9),
        rotation=(0.0, house_rotation_y, 0.0),
        scale=(1.0, 1.0, 1.0),
        environment=ENV_INTERNAL,
        diffuse_reflection=0.85,
        specular_reflection=0.25,
        shininess=24.0,
    ))

    # Piso da parte menor da casa.
    house_floor_mesh_2 = create_plane(
        width=8.0,
        depth=4.0,
        uv_repeat=4.0,
        texture_path=HOUSE_FLOOR_TEXTURE,
    )

    objects.append(SceneObject(
        name="piso_parte_2",
        mesh=house_floor_mesh_2,
        position=(-6.0, 0.08, 9.4),
        rotation=(0.0, house_rotation_y, 0.0),
        scale=(1.0, 1.0, 1.0),
        environment=ENV_INTERNAL,
        diffuse_reflection=0.85,
        specular_reflection=0.25,
        shininess=24.0,
    ))

    # -------------------------------------------------------------------------
    # Chão externo de grama
    # -------------------------------------------------------------------------
    grass_mesh = create_plane(
        width=120.0,
        depth=120.0,
        uv_repeat=20.0,
        texture_path=GRASS_TEXTURE,
    )

    objects.append(SceneObject(
        name="grama",
        mesh=grass_mesh,
        position=(0.0, -0.02, 0.0),
        rotation=(0.0, 0.0, 0.0),
        scale=(1.0, 1.0, 1.0),
        environment=ENV_EXTERNAL,
        diffuse_reflection=0.9,
        specular_reflection=0.05,
        shininess=8.0,
    ))

    # -------------------------------------------------------------------------
    # Objetos internos
    # -------------------------------------------------------------------------

    add_model_object(
        objects=objects,
        name="sofa_interno",
        filename="sofa/HSM0012.obj",
        target_size=5.0,
        target_center=(5.0, -1.0, -0.5),
        rotation=(-90.0, 90.0, 0.0),
        environment=ENV_INTERNAL,
        diffuse_reflection=0.7,
        specular_reflection=0.18,
        shininess=18.0,
        optional=True,
    )

    add_model_object(
        objects=objects,
        name="mesa_interna",
        filename="mesa/mesa.obj",
        target_size=2.2,
        target_center=(8.0, 0.10, -0.5),
        rotation=(0.0, 0.0, 0.0),
        environment=ENV_INTERNAL,
        diffuse_reflection=0.75,
        specular_reflection=0.35,
        shininess=32.0,
        optional=True,
    )

    add_model_object(
        objects=objects,
        name="mesa_cozinha_interna",
        filename="mesa_cozinha/SET1.obj",
        target_size=5.5,
        target_center=(-3.0, 0.10, 0.4),
        rotation=(0.0, 0.0, 0.0),
        environment=ENV_INTERNAL,
        diffuse_reflection=0.78,
        specular_reflection=0.28,
        shininess=28.0,
        optional=True,
    )

    add_model_object(
        objects=objects,
        name="retro_tv_interna",
        filename="retro_tv/retro_tv.obj",
        target_size=1.7,
        target_center=(8.0, 1.3, -0.5),
        rotation=(0.0, -90.0, 0.0),
        environment=ENV_INTERNAL,
        diffuse_reflection=0.6,
        specular_reflection=0.55,
        shininess=64.0,
        optional=True,
    )

    add_model_object(
        objects=objects,
        name="pessoa_interna",
        filename="pessoa/human.obj",
        target_size=4.0,
        target_center=(-5.0, 0.10, -2.0),
        rotation=(0.0, 180.0, 0.0),
        environment=ENV_INTERNAL,
        diffuse_reflection=0.7,
        specular_reflection=0.2,
        shininess=24.0,
        optional=True,
    )

    add_model_object(
        objects=objects,
        name="lareira",
        filename="lareira/13110_Fireplace_v2_l3.obj",
        target_size=5.0,
        target_center=(-7.9, -2.0, 0.0),
        rotation=(270.0, 90.0, 0.0),
        environment=ENV_INTERNAL,
        diffuse_reflection=0.72,
        specular_reflection=0.22,
        shininess=20.0,
        optional=True,
    )
    add_model_object(
    objects=objects,
    name="lampada_teto",
    filename="lampada/uploads_files_1973724_Salamp+By+Ihor+Harvylenko_Corona.obj",
    target_size=1.2,
    target_center=(0.0, 7.8, -2.0),
    rotation=(0.0, 0.0, 0.0),
    environment=ENV_INTERNAL,
    diffuse_reflection=0.7,
    specular_reflection=0.45,
    shininess=48.0,
    optional=True,
    )
    # -------------------------------------------------------------------------
    # Objetos externos
    # -------------------------------------------------------------------------

    # TRANSLAÇÃO: carro com I/J/K/L.
    controls.translating_object = add_model_object(
        objects=objects,
        name="carro",
        filename="carro/Generic_Old_Car.obj",
        target_size=10.2,
        target_center=(4.0, 0.10, 16.6),
        rotation=(0.0, 180.0, 0.0),
        environment=ENV_EXTERNAL,
        diffuse_reflection=0.62,
        specular_reflection=0.65,
        shininess=72.0,
        optional=True,
    )

    add_model_object(
        objects=objects,
        name="Galinha",
        filename="galinha/Chicken_Quad.obj",
        target_size=1.7,
        target_center=(-10.0, 0.10, 20.0),
        rotation=(0.0, -90.0, 0.0),
        environment=ENV_EXTERNAL,
        diffuse_reflection=0.8,
        specular_reflection=0.12,
        shininess=14.0,
        optional=True,
    )

    add_model_object(
        objects=objects,
        name="vaca",
        filename="vaca/Cow_Low_Poly.obj",
        target_size=4.0,
        target_center=(-5.0, 0.10, 15.0),
        rotation=(0.0, -90.0, 0.0),
        environment=ENV_EXTERNAL,
        diffuse_reflection=0.78,
        specular_reflection=0.16,
        shininess=18.0,
        optional=True,
    )

    headlight_marker = SceneObject(
    name="farol_carro_marcador",
    mesh=create_colored_cube(0.18, (1.0, 0.88, 0.45)),
    position=(4.0, 1.0, 13.2),
    rotation=(0.0, 0.0, 0.0),
    scale=(1.0, 1.0, 1.0),
    environment=ENV_EXTERNAL,
    diffuse_reflection=1.0,
    specular_reflection=0.0,
    emissive=True,
    emissive_color=(1.0, 0.88, 0.35),
    follow_object=controls.translating_object,
    follow_offset=(-1.1, 1.05, -4.15),
    )
    objects.append(headlight_marker)

   

    fireplace_marker = SceneObject(
        name="luz_lareira_marcador",
        mesh=create_colored_cube(0.65, (1.0, 0.32, 0.08)),
        position=(-8.9, 1.15, 0.0),
        rotation=(0.0, 0.0, 0.0),
        scale=(1.0, 1.0, 1.0),
        environment=ENV_INTERNAL,
        diffuse_reflection=1.0,
        specular_reflection=0.0,
        emissive=True,
        emissive_color=(1.0, 0.35, 0.08),
    )

    ceiling_marker = SceneObject(
        name="luz_teto_marcador",
        mesh=create_colored_cube(0.25, (1.0, 0.72, 0.36)),
        position=(0.0, 7.55, -2.0),
        rotation=(0.0, 0.0, 0.0),
        scale=(1.0, 1.0, 1.0),
        environment=ENV_INTERNAL,
        diffuse_reflection=1.0,
        specular_reflection=0.0,
        emissive=True,
        emissive_color=(1.0, 0.72, 0.36),
    )

    controls.lighting = LightingState(
        lights=[
            LightSource(
                name="Farol do carro",
                position=headlight_marker.position,
                color=(1.0, 0.88, 0.45),
                environment=ENV_EXTERNAL,
                marker_object=headlight_marker,
                attached_object=controls.translating_object,
                offset=(-1.1, 1.05, -4.15),
            ),
           
            LightSource(
                name="Lareira",
                position=fireplace_marker.position,
                color=(1.0, 0.34, 0.08),
                environment=ENV_INTERNAL,
                marker_object=fireplace_marker,
            ),
           LightSource(
                name="Luz quente do teto",
                position=ceiling_marker.position,
                color=(1.0, 0.74, 0.38),
                environment=ENV_INTERNAL,
                marker_object=ceiling_marker,
            ),
        ],
    )

    return objects, controls
