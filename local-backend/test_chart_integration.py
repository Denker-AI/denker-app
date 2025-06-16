#!/usr/bin/env python3
"""
Test script to debug chart integration issues
"""
import os
import sys
import asyncio
import tempfile

# Add local paths
sys.path.append('mcp_local/servers/markdown_editor')

async def test_chart_integration():
    """Test if chart creation and markdown integration works."""
    try:
        from chart_generator import create_chart_from_data_tool
        from markdown_integration import add_chart_to_markdown
        from markdown_editor import create_markdown
        
        print("🧪 Testing chart integration...")
        
        # Step 1: Create a test markdown file
        test_content = """# Test Document

This is a test document for chart integration.

## Chart Section

The chart should appear below:

"""
        
        # Create temp file for testing
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write(test_content)
            md_file_path = f.name
            
        print(f"📄 Created test markdown file: {md_file_path}")
        
        # Step 2: Create a chart
        print("📊 Creating test chart...")
        chart_result = await create_chart_from_data_tool(
            chart_type='pie',
            data={
                'labels': ['Success', 'Pending', 'Failed'], 
                'datasets': [{'data': [60, 30, 10], 'backgroundColor': ['#28a745', '#ffc107', '#dc3545']}]
            },
            title='Test Status Distribution',
            filename='test_integration_chart.png'
        )
        
        print(f"Chart creation result: {chart_result}")
        
        if not chart_result.get('success'):
            print(f"❌ Chart creation failed: {chart_result.get('error')}")
            return False
            
        print(f"✅ Chart created successfully at: {chart_result.get('chart_path')}")
        
        # Step 3: Add chart to markdown
        print("🔗 Adding chart to markdown...")
        integration_result = await add_chart_to_markdown(
            markdown_file=md_file_path,
            chart_data=chart_result,
            position=None,  # Append
            alt_text="Test Status Chart"
        )
        
        print(f"Integration result: {integration_result}")
        
        if not integration_result.get('success'):
            print(f"❌ Chart integration failed: {integration_result.get('error')}")
            return False
        
        # Step 4: Verify the markdown file was updated
        print("🔍 Verifying markdown file...")
        with open(md_file_path, 'r') as f:
            updated_content = f.read()
            
        print("📋 Updated markdown content:")
        print("=" * 50)
        print(updated_content)
        print("=" * 50)
        
        # Check if chart reference was added
        if 'test_integration_chart.png' in updated_content or chart_result.get('chart_path', '').split('/')[-1] in updated_content:
            print("✅ Chart reference found in markdown file!")
            success = True
        else:
            print("❌ Chart reference NOT found in markdown file!")
            success = False
        
        # Cleanup
        try:
            os.unlink(md_file_path)
            chart_path = chart_result.get('chart_path')
            if chart_path and os.path.exists(chart_path):
                os.unlink(chart_path)
        except:
            pass
            
        return success
            
    except Exception as e:
        print(f"❌ Exception during integration test: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("Testing chart integration...")
    success = asyncio.run(test_chart_integration())
    
    if success:
        print("\n🎉 Chart integration test PASSED!")
    else:
        print("\n💥 Chart integration test FAILED!")
    
    sys.exit(0 if success else 1) 