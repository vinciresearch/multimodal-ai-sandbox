from neo4j import GraphDatabase
import json
import re
from openai import OpenAI

client = OpenAI(
    api_key=os.environ.get("UE_OPENAI_API_KEY"), 
)

# Neo4j setup
driver = GraphDatabase.driver(
    "bolt://localhost:7687",
    auth=("neo4j", "multimodalGraph25")  # same password you set
)

GRAPH_SCHEMA = """
{
  "entities": [
    {
      "type": "Agent",
      "required_attributes": ["name", "role", "image_url (optional)"]
    },
    {
      "type": "Object",
      "required_attributes": ["name", "type_label", "image_url (optional)"]
    },
    {
      "type": "Location",
      "required_attributes": ["name", "address/coordinates", "image_url (optional)"]
    },
    {
      "type": "Event",
      "required_attributes": ["name", "type_label", "timestamp (optional)", "description (optional)", "media_url (optional)"]
    }
  ],
  "relationships": [
    {
      "type": "PERFORMS",
      "source_type": "Agent",
      "target_type": "Event"
    },
    {
      "type": "OCCURS_AT",
      "source_type": "Event",
      "target_type": "Location"
    },
    {
      "type": "INVOLVES",
      "source_type": "Event",
      "target_type": "Object"
    },
    {
      "type": "OWNS",
      "source_type": "Agent",
      "target_type": "Object"
    },
    {
      "type": "LOCATED_IN",
      "source_type": "Object",
      "target_type": "Location"
    },
    {
      "type": "NEXT_EVENT",
      "source_type": "Event",
      "target_type": "Event"
    }
  ]
}

"""

# Function to create prompt dynamically
def generate_multimodal_prompt(input_data, existing_graph=None):
    """
    Builds a dynamic prompt to create or update a multimodal knowledge graph 
    from text, images, and image-caption pairs.
    """

    instructions = ""

    # Define action: create or update
    if existing_graph is None:
        instructions += "Create "
    else:
        instructions += "Update "

    instructions += (
        "a structured multimodal knowledge graph based on the provided schema and input data. "
        "The input may include text, images, or image-caption pairs. "
        "You have access to the **actual content of images** and can visually interpret them, not just their URLs.\n\n"
    )

    instructions += "### TASK:\n"
    if existing_graph is None:
        instructions += (
            "- Draft the initial knowledge graph in **pure JSON format** based on the input data.\n"
            "- Include **entities** (with attributes) and **relationships** (linking entities) as required by the schema.\n"
        )
    else:
        instructions += (
            "- Modify the provided existing knowledge graph to incorporate the new input data.\n"
            "- **Preserve** all existing nodes and relationships unless explicitly stated otherwise.\n"
            "- IMPORTANT: **Do not duplicate** previously added elements.\n"
            "- Add **nodes**, **attributes**, and **relationships** as needed to integrate new information.\n"
            "- ALWAYS meaningfully **link new entities TO ENTITIES IN THE EXISTING GRAPH** via relationships.\n"
            "- Ensure consistency with the existing graph structure.\n\n"
            "Here is the existing knowledge graph:\n\n" + existing_graph + "\n"
        )

    instructions += (
        "\n\n### Schema for the Knowledge Graph\n"
        f"{GRAPH_SCHEMA}\n"
    )

    instructions += (
        "\n\n### Input Data\n"
        f"{input_data}\n"
    )

    instructions += (
        "\n\n### Guidelines for Graph Construction\n"
        "- Focus on modeling the **process** and **sequence of events**.\n"
        "- Always link agents, events, objects, and locations meaningfully.\n"
        "- **For images**, visually interpret the content and:\n"
        "  - Identify relevant **objects**, **agents**, **events**, or **locations**.\n"
        "  - If a recognizable action or event is depicted, create an **Event** node.\n"
        "  - If a recognizable object is depicted (e.g., drone, vehicle, building, artifact), create an **Object** node.\n"
        "  - If people are shown, create an **Agent** node (if identifiable) or a generic one.\n"
        "  - Always attach the `image_url` as an attribute of the corresponding node.\n"
        "- If captions are provided, treat them as **primary textual information**.\n"
        "- If timestamps are mentioned (explicitly or inferred from images, metadata, context), add them to Events.\n"
        "- Use the **NEXT_EVENT** relationship to indicate sequential processes when applicable.\n"
        "- If the new entity (e.g., a piece of equipment, a location, or an event) is clearly related to an existing one (e.g., a previously defined Agent, Event, or Procedure), link them using the appropriate relationship type (e.g., INVOLVES, OWNS, PERFORMS, LOCATED_IN).\n"
        "- Always aim to integrate new information into the existing structure by creating meaningful connections.\n"
        "- Avoid creating isolated nodes unless the entity truly has no connection.\n"
        "- Prefer reusing or extending existing events, procedures, or agents if the new entity fits within their context.\n"

    )

    instructions += (
        "\n\n### STRICT CONSTRAINTS for Output Formatting\n"
        "- **Entities**:\n"
        "- Only use `type` values exactly as defined: `Agent`, `Object`, `Location`, `Event`.\n"
        "- Do not invent new types like `Person`.\n"
        "- Do not include `id` fields.\n"
        "- Attributes must be **flattened**: put all attributes (e.g., `name`, `role`, `image_url`) directly inside the entity dictionary.\n"
        "- **Relationships**:\n"
        "- Use only the exact relationship types specified: `PERFORMS`, `OCCURS_AT`, `INVOLVES`, `OWNS`, `LOCATED_IN`, `NEXT_EVENT`.\n"
        "- Do not invent relationship types like `PARTICIPATES_IN`.\n"
        "- Use `source` and `target` fields containing the **entity names**, not IDs.\n"
        "- **General**:\n"
        "- No null values. Omit fields if no data is available.\n"
        "- Do not include any IDs, UUIDs, or auto-generated identifiers.\n"
    )

    instructions += (
        "\n\n### Acceptability Criteria\n"
        "- Output must be **pure JSON** matching the provided schema exactly.\n"
        "- No comments, explanations, or natural language outside the JSON.\n"
        "- Ensure clean structure: all nodes and relationships properly typed and connected.\n"
        "- Do not hallucinate or fabricate information not present in the input data.\n"
    )

    return instructions



def clean_json_output(raw_output):
    # Remove triple backticks and any language hints like ```json
    clean = re.sub(r"^```[a-zA-Z0-9]*\n?", "", raw_output.strip())
    clean = re.sub(r"```$", "", clean.strip())
    return clean


# Query LLM and get structured JSON
def extract_graph_data(prompt_text=None, image_url=None):

    messages = []

    if image_url:
        # True multimodal message
        messages.append({
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {"url": image_url}
                },
                {
                    "type": "text",
                    "text": prompt_text
                }
            ]
        })
    else:
        # Text-only message
        messages.append({
            "role": "user",
            "content": prompt_text
        })

    
    response = client.chat.completions.create(
        messages=messages,
        model="gpt-4o",
        temperature=0.3
    )

    raw_output = response.choices[0].message.content
    print("LLM output: ")
    print(raw_output)
    cleaned_output = clean_json_output(raw_output)
    parsed_output = json.loads(cleaned_output)

    return parsed_output

# Insert data into Neo4j
import re

def insert_into_neo4j(data):
    with driver.session() as session:
        for entity in data.get("entities", []):
            entity_type = entity.get("type")
            entity_name = entity.get("name")

            flat_attributes = {}

            # Flatten nested attributes if present
            if "attributes" in entity and isinstance(entity["attributes"], dict):
                flat_attributes.update(entity["attributes"])

            # Include top-level keys except type, name, and attributes
            for k, v in entity.items():
                if k not in ["type", "name", "attributes"]:
                    flat_attributes[k] = v

            query = f"MERGE (n:{entity_type} {{name: $name}})"
            params = {"name": entity_name}

            if flat_attributes:
                set_clauses = []
                for key, value in flat_attributes.items():
                    safe_key = re.sub(r"[^a-zA-Z0-9_]", "_", key)
                    param_key = f"param_{safe_key}"
                    set_clauses.append(f"n.{safe_key} = ${param_key}")
                    params[param_key] = value
                query += " SET " + ", ".join(set_clauses)

            session.run(query, **params)

        for rel in data.get("relationships", []):
            session.run(
                f"""
                MATCH (a {{name: $source}}), (b {{name: $target}})
                MERGE (a)-[r:{rel['type']}]->(b)
                """,
                source=rel["source"],
                target=rel["target"]
            )


def serialize_current_graph():
    """
    Serialize the current state of the graph into a JSON format 
    compatible with the prompt expectations.
    """
    with driver.session() as session:
        nodes_query = "MATCH (n) RETURN n"
        relationships_query = "MATCH (a)-[r]->(b) RETURN a.name AS source, type(r) AS type, b.name AS target"

        nodes = session.run(nodes_query)
        relationships = session.run(relationships_query)

        serialized = {
            "entities": [],
            "relationships": []
        }

        for record in nodes:
            node = record["n"]
            serialized["entities"].append({
                "type": list(node.labels)[0],
                "name": node.get("name"),
                "attributes": {k: v for k, v in dict(node).items() if k != "name"}
            })

        for record in relationships:
            serialized["relationships"].append({
                "type": record["type"],
                "source": record["source"],
                "target": record["target"],
                "attributes": {}  # optional: if your relationships have properties
            })

        return json.dumps(serialized, indent=2)


# Main Workflow
def multimodal_graph_builder(data_points):
    """
    Iteratively builds or updates a multimodal knowledge graph
    from a list of text, image, or image-caption inputs.
    """

    existing_graph = None  # Holds serialized graph JSON for iterative updates

    for idx, data_point in enumerate(data_points):
        print(f"\nProcessing data point {idx+1}:")

        input_description = ""
        image_url = None

        # 1. Prepare the input description and detect if image is involved
        if data_point['type'] == 'text':
            input_description = f"Text Input:\n{data_point['data']}"
        elif data_point['type'] == 'image':
            input_description = f"Image Input URL:\n{data_point['data']}"
            image_url = data_point['data']
        elif data_point['type'] == 'image_caption':
            input_description = f"Image Input URL:\n{data_point['data']}\nCaption:\n{data_point['caption']}"
            image_url = data_point['data']
        else:
            raise ValueError(f"Unsupported input type: {data_point['type']}")

        # 2. Generate the detailed prompt
        prompt_text = generate_multimodal_prompt(input_description, existing_graph)

        print("Using prompt:")
        print(prompt_text)
       
        # 3. Query the LLM and get the extracted structured data
        graph_data = extract_graph_data(prompt_text=prompt_text, image_url=image_url)

        print("Adding data to Neo4j...")

        # 4. Insert new data into Neo4j
        insert_into_neo4j(graph_data)

        # 5. Update the existing_graph JSON for next iteration
        existing_graph = serialize_current_graph()


# Example usage
data_points = [
    {"type": "text", "data": "As per the Safety and Health Magazine, the Electrical Safety Foundation International (ESFI) found that workers in the construction and extraction industries accounted for 40%, and those in installation, maintenance, and repair work accounted for 20% of electrical fatalities caused by electrical hazards and risks.\nElectrical hazards can include electric shock, burns, arc flashes (sudden releases of intense energy during electrical faults or short circuits), and arc blasts, which can occur during tasks like electrical installation, maintenance, troubleshooting, or repair. In this regard, the proper and safe use of PPE serves as a barrier between the worker and the electrical energy, preventing or minimizing the impact of potential hazards.\nAside from playing a crucial role in ensuring worker safety, here are more reasons why PPE for electrical safety must be prioritized:\nProtection Against Electrical Shock – Electrical PPEs, like insulated gloves and voltage-rated tools, are designed to withstand and insulate against the voltage levels present in electrical systems.\nPrevention of Burns and Arc Flashes – Flame-resistant clothing and arc flash suits help resist ignition, reduce the extent of burns, and provide thermal protection in case of an arc flash incident.\nReduction of Electrical Contact Injuries – Electrical PPE, like safety shoes with non-conductive soles and insulating mats, provides insulation and prevents the flow of electric current through the worker’s body, reducing the severity of injuries in case of an electrical fault.\nCompliance with Safety Regulations – Workers and employers can ensure compliance with relevant regulations in countries and states to maintain a safe work environment.\nRisk Mitigation – Electrical PPE acts as an additional layer of protection, reducing the likelihood of accidents and injuries and the overall risk associated with electrical work."},
    {"type": "image", "data": "https://cdn.shopify.com/s/files/1/0786/4523/1934/files/Type-II-Helmets_02-properties.png"}
]

multimodal_graph_builder(data_points)
