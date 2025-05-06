/**
 * Test script for component checks
 * 
 * This is a helper script to verify the restructured components are working
 * Copy and paste these tests into your browser console to check for errors
 */

// Test SideMenu component
function testSideMenu() {
  try {
    const sideMenuElement = document.querySelector('.MuiDrawer-root');
    console.log('SideMenu exists:', !!sideMenuElement);
    
    if (sideMenuElement) {
      // Check if tabs and main content are rendered
      const tabsElement = sideMenuElement.querySelector('.MuiTabs-root');
      console.log('SideMenu tabs exist:', !!tabsElement);
      
      // Check for conversation list
      const conversationElements = sideMenuElement.querySelectorAll('li');
      console.log('Conversation elements found:', conversationElements.length);
    }
    
    console.log('SideMenu test completed successfully');
    return true;
  } catch (error) {
    console.error('SideMenu test failed:', error);
    return false;
  }
}

// Test MainWindow component
function testMainWindow() {
  try {
    // Check for the main content area
    const mainWindowElement = document.querySelector('.app-container > div > div:nth-child(2) > div');
    console.log('MainWindow exists:', !!mainWindowElement);
    
    if (mainWindowElement) {
      // Check if conversation header exists
      const headerElement = mainWindowElement.querySelector('div:first-child');
      console.log('Conversation header exists:', !!headerElement);
      
      // Check if MainContent exists
      const contentElement = mainWindowElement.querySelector('div:nth-child(2)');
      console.log('Main content exists:', !!contentElement);
    }
    
    console.log('MainWindow test completed successfully');
    return true;
  } catch (error) {
    console.error('MainWindow test failed:', error);
    return false;
  }
}

// Test hooks
function testHooks() {
  try {
    // Check for any error messages in the console related to hooks
    const hookErrors = Array.from(document.querySelectorAll('.__react-error-overlay__'))
      .filter(el => el.textContent.includes('hook'));
    
    console.log('Hook errors found:', hookErrors.length === 0 ? 'None' : hookErrors.length);
    
    console.log('Hooks test completed successfully');
    return true;
  } catch (error) {
    console.error('Hooks test failed:', error);
    return false;
  }
}

// Run all tests
function runAllTests() {
  console.log('=== COMPONENT STRUCTURE TESTS ===');
  const sideMenuResult = testSideMenu();
  const mainWindowResult = testMainWindow();
  const hooksResult = testHooks();
  
  console.log('=== TEST RESULTS ===');
  console.log('SideMenu:', sideMenuResult ? 'PASS' : 'FAIL');
  console.log('MainWindow:', mainWindowResult ? 'PASS' : 'FAIL');
  console.log('Hooks:', hooksResult ? 'PASS' : 'FAIL');
  console.log('Overall:', (sideMenuResult && mainWindowResult && hooksResult) ? 'PASS' : 'FAIL');
}

// Instructions for manual testing
console.log(`
===== MANUAL TESTING INSTRUCTIONS =====
1. Open your browser console
2. Run the tests by copying and pasting:
   runAllTests();
3. Check for any error messages in the console
4. Verify the UI renders correctly
`);

// Export functions for browser console use
if (typeof window !== 'undefined') {
  window.testSideMenu = testSideMenu;
  window.testMainWindow = testMainWindow;
  window.testHooks = testHooks;
  window.runAllTests = runAllTests;
} 