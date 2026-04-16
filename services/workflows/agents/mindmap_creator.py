"""
MindmapCreatorAgent: Creates visual mind maps for concept organization

Responsibilities:
- Organize concepts hierarchically
- Create relationships between concepts
- Generate visual structure
"""

from typing import Any, Dict, List
import logging
from ..base import BaseAgent
from ..config import ContentLevel

logger = logging.getLogger(__name__)


class MindmapCreatorAgent(BaseAgent):
    """
    Creates mind maps to visualize concept relationships and learning structure.
    Ideal for visual learners and holistic understanding.
    """
    
    def __init__(self):
        super().__init__(name="MindmapCreatorAgent", timeout=25)
    
    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate mind map structure.
        
        Input:
            - topic: str
            - subtopics: list[str]
            - learning_objectives: list[str]
            - difficulty: ContentLevel
            - max_depth: int (default 3)
            
        Output:
            - mindmap_structure: dict - hierarchical structure
            - nodes: list[dict] - all nodes in the map
            - connections: list[dict] - relationships between nodes
            - json_format: str - JSON representation for rendering
            - quality_score: float
        """
        topic = input_data.get("topic", "")
        subtopics = input_data.get("subtopics", [])
        learning_objectives = input_data.get("learning_objectives", [])
        difficulty = input_data.get("difficulty", ContentLevel.INTERMEDIATE)
        max_depth = input_data.get("max_depth", 3)
        
        # Create central concept
        root_node = await self._create_root_node(topic)
        
        # Create main branches from subtopics
        nodes = [root_node]
        connections = []
        
        # Add primary branches (subtopics)
        primary_nodes, primary_connections = await self._create_primary_branches(
            topic=topic,
            subtopics=subtopics,
            difficulty=difficulty
        )
        nodes.extend(primary_nodes)
        connections.extend(primary_connections)
        
        # Add secondary nodes for details
        if max_depth > 1:
            secondary_nodes, secondary_connections = await self._create_secondary_branches(
                primary_nodes=primary_nodes,
                learning_objectives=learning_objectives,
                difficulty=difficulty
            )
            nodes.extend(secondary_nodes)
            connections.extend(secondary_connections)
        
        # Create hierarchical structure
        mindmap_structure = await self._build_hierarchical_structure(
            root=root_node,
            nodes=nodes,
            connections=connections
        )
        
        # Calculate quality
        quality_score = await self._calculate_quality_score(nodes, connections)
        
        # Generate JSON for rendering
        json_format = await self._generate_json_format(mindmap_structure)
        
        return {
            "topic": topic,
            "mindmap_structure": mindmap_structure,
            "nodes": nodes,
            "connections": connections,
            "total_nodes": len(nodes),
            "total_connections": len(connections),
            "max_depth": max_depth,
            "json_format": json_format,
            "quality_score": quality_score,
            "difficulty": difficulty,
        }
    
    async def validate_input(self, input_data: Dict[str, Any]) -> bool:
        """Validate input"""
        required_fields = ["topic", "subtopics"]
        for field in required_fields:
            if field not in input_data:
                raise ValueError(f"Missing required field: {field}")
        return True
    
    async def _create_root_node(self, topic: str) -> Dict[str, Any]:
        """Create the central topic node"""
        return {
            "id": "root",
            "label": topic,
            "type": "root",
            "depth": 0,
            "color": "#FF6B6B",  # Red for root
            "children": []
        }
    
    async def _create_primary_branches(self, topic: str, subtopics: List[str],
                                      difficulty: ContentLevel) -> tuple:
        """Create primary branches from subtopics"""
        nodes = []
        connections = []
        color_map = ["#4ECDC4", "#45B7D1", "#FFA502", "#2ECC71", "#9B59B6"]
        
        for i, subtopic in enumerate(subtopics):
            node_id = f"primary_{i}"
            node = {
                "id": node_id,
                "label": subtopic,
                "type": "primary",
                "depth": 1,
                "color": color_map[i % len(color_map)],
                "children": [],
                "description": f"Subtopic: {subtopic}"
            }
            nodes.append(node)
            
            # Create connection from root to this node
            connection = {
                "source": "root",
                "target": node_id,
                "type": "primary_connection",
                "label": "explores"
            }
            connections.append(connection)
        
        return nodes, connections
    
    async def _create_secondary_branches(self, primary_nodes: List[Dict],
                                        learning_objectives: List[str],
                                        difficulty: ContentLevel) -> tuple:
        """Create secondary nodes for detail and depth"""
        nodes = []
        connections = []
        
        secondary_colors = ["#E1F5FE", "#F3E5F5", "#FFF3E0"]
        
        for prim_node in primary_nodes:
            # Find related objectives
            related_objectives = [
                obj for obj in learning_objectives 
                if prim_node["label"].lower() in obj.lower()
            ]
            
            # Create secondary nodes (max 3 per primary)
            for j, objective in enumerate(related_objectives[:3]):
                node_id = f"{prim_node['id']}_secondary_{j}"
                
                node = {
                    "id": node_id,
                    "label": objective.split(":")[-1].strip()[:50],  # Shortened label
                    "type": "secondary",
                    "depth": 2,
                    "color": secondary_colors[j % len(secondary_colors)],
                    "parent": prim_node["id"],
                }
                nodes.append(node)
                
                # Create connection
                connection = {
                    "source": prim_node["id"],
                    "target": node_id,
                    "type": "secondary_connection",
                    "label": "includes"
                }
                connections.append(connection)
        
        return nodes, connections
    
    async def _build_hierarchical_structure(self, root: Dict, nodes: List[Dict],
                                           connections: List[Dict]) -> Dict:
        """Build the complete hierarchical structure"""
        structure = root.copy()
        
        # Build tree recursively
        def build_tree(parent_id):
            children = []
            for connection in connections:
                if connection["source"] == parent_id:
                    target_node = next(
                        (n for n in nodes if n["id"] == connection["target"]),
                        None
                    )
                    if target_node:
                        child = target_node.copy()
                        child["connection_label"] = connection.get("label", "")
                        child["children"] = build_tree(target_node["id"])
                        children.append(child)
            return children
        
        structure["children"] = build_tree("root")
        return structure
    
    async def _calculate_quality_score(self, nodes: List[Dict],
                                      connections: List[Dict]) -> float:
        """Calculate quality based on structure completeness"""
        if not nodes or not connections:
            return 0.0
        
        # Score based on:
        # 1. Number of nodes (should have at least 5)
        # 2. Connections per node (should average 2+)
        # 3. Depth variety
        
        node_score = min(1.0, len(nodes) / 10)
        connection_ratio = len(connections) / len(nodes) if nodes else 0
        connection_score = min(1.0, connection_ratio / 2)
        
        avg_score = (node_score + connection_score) / 2
        return min(1.0, max(0.0, avg_score))
    
    async def _generate_json_format(self, structure: Dict) -> str:
        """
        Generate JSON format suitable for D3.js or other visualization libraries
        Format: {name, value, children}
        """
        def convert_node(node):
            return {
                "name": node.get("label", ""),
                "id": node.get("id", ""),
                "color": node.get("color", "#999"),
                "children": [convert_node(child) for child in node.get("children", [])],
            }
        
        json_obj = convert_node(structure)
        
        # Remove empty children arrays for cleaner output
        def clean_obj(obj):
            if "children" in obj and not obj["children"]:
                del obj["children"]
            if "children" in obj:
                obj["children"] = [clean_obj(child) for child in obj["children"]]
            return obj
        
        cleaned = clean_obj(json_obj)
        
        # Convert to JSON string (in real implementation use json.dumps)
        import json
        return json.dumps(cleaned, indent=2)
