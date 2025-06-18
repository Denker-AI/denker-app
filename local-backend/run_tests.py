#!/usr/bin/env python3
"""
Test Runner for Markdown Editor MCP Server

This script:
1. Checks if we're in a virtual environment
2. Installs required dependencies if needed
3. Runs the comprehensive test suite

Usage:
    python run_tests.py
"""

import os
import sys
import subprocess
import venv
from pathlib import Path

def is_venv():
    """Check if we're running in a virtual environment"""
    return (hasattr(sys, 'real_prefix') or 
            (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix))

def check_dependencies():
    """Check if required dependencies are installed"""
    required_packages = ['aiohttp', 'requests', 'pillow', 'pandas', 'python-dotenv']
    missing = []
    
    for package in required_packages:
        try:
            if package == 'python-dotenv':
                __import__('dotenv')
            else:
                __import__(package)
        except ImportError:
            missing.append(package)
    
    return missing

def check_api_keys():
    """Check if API keys are configured"""
    import os
    
    # Load .env file like the test does
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    
    print("\n🔑 Checking API Configuration...")
    
    unsplash_key = os.getenv('UNSPLASH_ACCESS_KEY')
    if unsplash_key:
        print(f"✅ Unsplash API key found: {unsplash_key[:10]}...")
    else:
        print("⚠️  Unsplash API key not found")
        print("   Photo download tests will be skipped")
        print("   💡 Get a free API key from: https://unsplash.com/developers")
        print("   💡 Set with: export UNSPLASH_ACCESS_KEY=your_key_here")
        print("   💡 Or add to .env file: UNSPLASH_ACCESS_KEY=your_key_here")
    
    # Could check other API keys here if needed
    return {"unsplash": bool(unsplash_key)}

def install_dependencies(packages):
    """Install missing dependencies"""
    print(f"📦 Installing missing dependencies: {', '.join(packages)}")
    
    try:
        subprocess.check_call([
            sys.executable, '-m', 'pip', 'install', '-q'
        ] + packages)
        print("✅ Dependencies installed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install dependencies: {e}")
        return False

def run_tests():
    """Run the comprehensive test suite"""
    print("🚀 Running Markdown Editor Comprehensive Tests")
    print("="*60)
    
    try:
        # Import and run the test
        import asyncio
        sys.path.append(os.path.dirname(__file__))
        
        from test_markdown_editor_comprehensive import main
        asyncio.run(main())
        
    except Exception as e:
        print(f"❌ Test execution failed: {e}")
        return False
    
    return True

def main():
    """Main runner function"""
    print("🔧 Markdown Editor Test Setup & Runner")
    print("="*50)
    
    # Check virtual environment
    if is_venv():
        print("✅ Running in virtual environment")
    else:
        print("⚠️  Not in virtual environment")
        print("   Recommendation: Create and activate a venv first:")
        print("   python -m venv test_env")
        print("   source test_env/bin/activate  # On Windows: test_env\\Scripts\\activate")
        print("   Then run this script again")
        
        response = input("\n   Continue anyway? (y/N): ").strip().lower()
        if response != 'y':
            print("Exiting...")
            return
    
    # Check dependencies
    missing_deps = check_dependencies()
    if missing_deps:
        print(f"📋 Missing dependencies: {', '.join(missing_deps)}")
        
        auto_install = input("   Install automatically? (Y/n): ").strip().lower()
        if auto_install != 'n':
            if not install_dependencies(missing_deps):
                print("Failed to install dependencies. Please install manually:")
                print(f"   pip install {' '.join(missing_deps)}")
                return
        else:
            print("Please install dependencies manually:")
            print(f"   pip install {' '.join(missing_deps)}")
            return
    else:
        print("✅ All dependencies available")
    
    # Check API keys
    api_status = check_api_keys()
    
    # Run tests
    print("\n" + "="*50)
    success = run_tests()
    
    print("\n" + "="*50)
    if success:
        print("🎉 Test run completed!")
        print("\n💡 Tips for agents:")
        print("   • Use size='regular' for most photos (good balance)")
        print("   • Use size='large' for hero images or detailed photos")
        print("   • Use size='small' for thumbnails or sidebar images")
        print("   \n📊 Table System:")
        print("   • create_table_with_theme() creates Markdown tables with styling")
        print("   • Available themes: professional, modern, elegant, minimal, bold, colorful")
        print("   • create_csv_document() creates Excel-compatible CSV files") 
        print("   • Tables support Unicode, emojis, and custom alignment")
        print("   • Markdown tables can be converted to PDF/DOCX with styling")
        print("   \n🌍 Unicode Support:")
        print("   • Full emoji support in documents and tables: 🎉📊💰🚀")
        print("   • International characters: 中文, العربية, Русский, 한국어")
        print("   • Currency symbols: €¥£₹$₩₪")
        print("   • Live preview and PDF conversion preserve Unicode")
        print("   \n📄 File Formats:")
        print("   • All files created in workspace with simple filenames") 
        print("   • Supports conversion to: HTML, PDF, DOCX, TXT, CSV")
    else:
        print("❌ Test run failed - check output above")

if __name__ == "__main__":
    main() 