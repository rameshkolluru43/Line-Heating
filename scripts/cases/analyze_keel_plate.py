"""
Analyze IGES keel plate geometry and generate line heating plan.

This script:
1. Extracts approximate dimensions from the IGES file
2. Recommends line heating patterns for the desired curvature
3. Calculates heat energy requirements
"""

from pathlib import Path
import re
import numpy as np
from python_prototype.line_heating.models import (
    LineGeometry,
    Material,
    PassProcess,
    Plate,
    Plan,
    Target,
    HeatingPass,
    Quench,
    SimulationSettings,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def parse_iges_bounds(iges_path: Path):
    """Extract approximate geometric bounds from IGES file."""
    print(f"\n{'='*60}")
    print(f"Analyzing IGES File: {iges_path.name}")
    print(f"{'='*60}\n")
    
    with open(iges_path, 'r') as f:
        content = f.read()
    
    # Extract coordinates from parameter section (lines starting with numbers and ending with P)
    coord_pattern = r'(-?\d+\.?\d*(?:E[+-]?\d+)?)'
    coords = []
    
    for line in content.split('\n'):
        if 'P' in line[-10:]:  # Parameter section
            matches = re.findall(coord_pattern, line)
            coords.extend([float(m) for m in matches if abs(float(m)) > 1.0])
    
    if not coords:
        print("⚠️  Could not extract coordinates from IGES file")
        return None
    
    coords = np.array(coords)
    
    # Filter reasonable plate dimensions (likely in mm)
    # Ship plates typically: 1000-100000 mm length, 10-50 mm thickness
    likely_length = coords[(coords > 1000) & (coords < 100000)]
    likely_thickness = coords[(coords > 10) & (coords < 100)]
    
    if len(likely_length) > 0:
        x_min, x_max = likely_length.min(), likely_length.max()
        length = x_max - x_min
        width = length  # Approximate if both dimensions similar
        
        print("📐 Extracted Dimensions:")
        print(f"   Length (X): {length:.1f} mm ({length/1000:.2f} m)")
        print(f"   Width (Y):  {width:.1f} mm ({width/1000:.2f} m)")
        
        if len(likely_thickness) > 0:
            thickness = np.median(likely_thickness)
            print(f"   Thickness:  {thickness:.1f} mm")
        else:
            thickness = 12.0  # Default ship plate thickness
            print(f"   Thickness:  {thickness:.1f} mm (assumed)")
        
        return {
            'length': float(length),
            'width': float(width),
            'thickness': float(thickness)
        }
    
    return None


def calculate_heat_requirements(plate_length, plate_width, thickness, num_lines):
    """Calculate heat energy requirements for line heating."""
    
    # Process parameters based on calibration
    torch_power_W = 12000  # Watts
    travel_speed_mm_s = 12.0  # mm/s
    footprint_width_mm = 18.0  # mm
    
    # Energy per mm
    line_energy_J_mm = torch_power_W / travel_speed_mm_s
    
    # Total energy per line
    energy_per_line_MJ = (line_energy_J_mm * plate_length) / 1e6
    
    # Time per line
    time_per_line_s = plate_length / travel_speed_mm_s
    time_per_line_min = time_per_line_s / 60.0
    
    # Total for all lines
    total_energy_MJ = energy_per_line_MJ * num_lines
    total_time_min = time_per_line_min * num_lines
    
    print(f"\n{'='*60}")
    print("🔥 HEAT REQUIREMENTS CALCULATION")
    print(f"{'='*60}\n")
    
    print("Process Parameters:")
    print(f"   Torch Power:    {torch_power_W/1000:.1f} kW")
    print(f"   Travel Speed:   {travel_speed_mm_s:.1f} mm/s")
    print(f"   Footprint:      {footprint_width_mm:.1f} mm")
    print(f"   Target Temp:    900-950°C (1173-1223K)")
    
    print(f"\nPer Line (Length: {plate_length:.0f} mm):")
    print(f"   Line Energy:    {line_energy_J_mm:.1f} J/mm")
    print(f"   Total Energy:   {energy_per_line_MJ:.2f} MJ")
    print(f"   Heating Time:   {time_per_line_min:.1f} minutes")
    
    print(f"\nFor {num_lines} Lines:")
    print(f"   Total Energy:   {total_energy_MJ:.1f} MJ")
    print(f"   Total Time:     {total_time_min:.1f} minutes ({total_time_min/60:.1f} hours)")
    print(f"   With cooling:   {total_time_min*1.5:.1f} minutes ({total_time_min*1.5/60:.1f} hours)")
    
    return {
        'power_W': torch_power_W,
        'speed_mm_s': travel_speed_mm_s,
        'footprint_mm': footprint_width_mm,
        'line_energy_J_mm': line_energy_J_mm,
        'energy_per_line_MJ': energy_per_line_MJ,
        'total_energy_MJ': total_energy_MJ,
        'time_per_line_min': time_per_line_min,
        'total_time_min': total_time_min
    }


def generate_line_heating_pattern(length, width, num_lines):
    """Generate recommended line heating pattern."""
    
    print(f"\n{'='*60}")
    print("📍 RECOMMENDED LINE HEATING PATTERN")
    print(f"{'='*60}\n")
    
    # Calculate line spacing
    line_spacing = width / (num_lines + 1)
    
    print(f"Pattern Configuration:")
    print(f"   Number of Lines:  {num_lines}")
    print(f"   Line Spacing:     {line_spacing:.1f} mm")
    print(f"   Orientation:      Longitudinal (parallel to length)")
    print(f"   Heating Side:     +z (top surface)")
    print(f"   Heating Mode:     Sequential")
    
    # Generate line positions
    lines = []
    for i in range(1, num_lines + 1):
        y_position = i * line_spacing
        line = {
            'id': f'L{i}',
            'name': f'longitudinal_{i}',
            'y_position': y_position,
            'start': (0.0, y_position),
            'end': (length, y_position)
        }
        lines.append(line)
    
    print(f"\nLine Positions (Y-coordinates):")
    for line in lines:
        print(f"   {line['id']:>4}: y = {line['y_position']:>8.1f} mm")
    
    return lines


def create_heating_plan(dims, num_lines=20):
    """Create a Plan object for the keel plate heating."""
    
    material = Material(
        grade="A36",
        E=210_000.0,  # MPa
        nu=0.3,
        alpha=1.2e-5,  # 1/K
        yield_strength=250.0,  # MPa
        steel_factor=1.0
    )
    
    plate = Plate(
        id="keel_plate",
        length=dims['length'],
        width=dims['width'],
        thickness=dims['thickness'],
        material=material,
        mesh_size=50.0  # Coarse mesh for large plate
    )
    
    # Target curvature (adjust based on IGES surface)
    target = Target(
        mode="radius",
        radius=15000.0  # 15m radius (typical ship hull curvature)
    )
    
    # Generate heating lines
    line_spacing = dims['width'] / (num_lines + 1)
    lines = []
    passes = []
    
    for i in range(1, num_lines + 1):
        y_pos = i * line_spacing
        line_id = f"L{i}"
        
        line = LineGeometry(
            id=line_id,
            name=f"longitudinal_{i}",
            type="straight",
            points=[(0.0, y_pos), (dims['length'], y_pos)],
            nominal_width=18.0,
            heated_side="+z"
        )
        lines.append(line)
        
        process = PassProcess(
            power_W=12_000.0,
            speed_mm_s=12.0,
            footprint_width_mm=18.0,
            repeats=1,
            quench=Quench(mode="water", lag_s=120.0, zones=[f"Z{i}"])
        )
        
        pass_obj = HeatingPass(
            id=f"P{i}",
            line_id=line_id,
            sequence_index=i,
            process=process
        )
        passes.append(pass_obj)
    
    simulation = SimulationSettings(
        model="mindlin_q4",
        boundary_condition="simply"
    )
    
    plan = Plan(
        meta_version="0.1.0",
        plate=plate,
        target=target,
        lines=lines,
        passes=passes,
        simulation=simulation
    )
    
    return plan


def main():
    """Main analysis function."""
    
    # Path to IGES file
    iges_file = REPO_ROOT / "IGESFiles" / "keel plate 0-5.igs"
    
    if not iges_file.exists():
        print(f"❌ IGES file not found: {iges_file}")
        return
    
    # Parse IGES file
    dims = parse_iges_bounds(iges_file)
    
    if dims is None:
        print("\n❌ Could not extract dimensions from IGES file")
        print("Using default keel plate dimensions:")
        dims = {
            'length': 3000.0,
            'width': 60000.0,
            'thickness': 12.0
        }
        print(f"   Length: {dims['length']:.1f} mm")
        print(f"   Width:  {dims['width']:.1f} mm")
        print(f"   Thickness: {dims['thickness']:.1f} mm")
    
    # For demonstration, use a smaller representative section
    print(f"\n{'='*60}")
    print("📝 NOTE: Using Representative Section for Analysis")
    print(f"{'='*60}")
    print("For computational efficiency, analyzing a 3m x 1m section")
    print("Scale results proportionally for full plate dimensions")
    
    # Use manageable dimensions
    analysis_dims = {
        'length': min(dims['length'], 3000.0),
        'width': min(dims['width'], 1000.0),
        'thickness': dims['thickness']
    }
    
    # Recommend number of lines based on width
    num_lines = int(analysis_dims['width'] / 200)  # One line per 200mm
    num_lines = max(5, min(num_lines, 20))  # Between 5 and 20 lines
    
    # Generate heating pattern
    lines = generate_line_heating_pattern(
        analysis_dims['length'],
        analysis_dims['width'],
        num_lines
    )
    
    # Calculate heat requirements
    heat_req = calculate_heat_requirements(
        analysis_dims['length'],
        analysis_dims['width'],
        analysis_dims['thickness'],
        num_lines
    )
    
    # Create plan
    print(f"\n{'='*60}")
    print("📋 GENERATING HEATING PLAN")
    print(f"{'='*60}\n")
    
    plan = create_heating_plan(analysis_dims, num_lines)
    
    # Save plan
    output_path = REPO_ROOT / "config" / "keel_plate_heating_plan.json"
    with open(output_path, 'w') as f:
        import json
        # Convert plan to dict (simplified)
        plan_dict = {
            'meta_version': plan.meta_version,
            'plate': {
                'id': plan.plate.id,
                'length': plan.plate.length,
                'width': plan.plate.width,
                'thickness': plan.plate.thickness
            },
            'num_lines': num_lines,
            'heat_requirements': heat_req,
            'lines': [
                {
                    'id': line.id,
                    'name': line.name,
                    'points': line.points
                }
                for line in plan.lines
            ]
        }
        json.dump(plan_dict, f, indent=2)
    
    print(f"✅ Heating plan saved to: {output_path}")
    
    print(f"\n{'='*60}")
    print("📊 SUMMARY")
    print(f"{'='*60}\n")
    print(f"IGES File:       {iges_file.name}")
    print(f"Plate Section:   {analysis_dims['length']:.0f} x {analysis_dims['width']:.0f} x {analysis_dims['thickness']:.0f} mm")
    print(f"Heating Lines:   {num_lines} longitudinal lines")
    print(f"Line Spacing:    {analysis_dims['width']/(num_lines+1):.1f} mm")
    print(f"Total Energy:    {heat_req['total_energy_MJ']:.1f} MJ")
    print(f"Process Time:    {heat_req['total_time_min']:.1f} min (heating only)")
    print(f"With Cooling:    {heat_req['total_time_min']*1.5:.1f} min ({heat_req['total_time_min']*1.5/60:.1f} hours)")
    print(f"\n{'='*60}\n")


if __name__ == "__main__":
    main()
