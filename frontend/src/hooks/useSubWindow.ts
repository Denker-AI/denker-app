import { useState, useCallback, useEffect } from 'react';
import type { CaptureData, Option, IntentionResponse } from '../types/types';

export const useSubWindow = () => {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [options, setOptions] = useState<Option[]>([]);
  const [captureData, setCaptureData] = useState<CaptureData | null>(null);
  const [apiResponse, setApiResponse] = useState<IntentionResponse | null>(null);
  
  useEffect(() => {
    console.log('🪟 Subwindow hook initialized');
    
    // Listen for API loading state changes
    const unsubscribeLoading = window.electron.onApiLoadingChange((isLoading) => {
      console.log('🔄 API loading state changed:', isLoading);
      setIsLoading(isLoading);
      
      // Clear error when starting a new request
      if (isLoading) {
        setError(null);
      }
    });
    
    // Handle initial capture data
    const handleCaptureData = async () => {
      try {
        console.log('📥 Waiting for capture data...');
        const data = await window.electron.waitForCaptureData();
        
        if (!data) {
          console.error('❌ No capture data received');
          setError('No capture data received from main process');
          return;
        }

        console.log('📥 Received capture data:', {
          mode: data.mode,
          hasText: !!data.text,
          textLength: data.text?.length || 0,
          textPreview: data.text?.substring(0, 100) + '...',
          hasScreenshot: !!data.screenshot,
          screenshotLength: data.screenshot?.length || 0,
          timestamp: data.timestamp,
          clipboardAge: data.clipboardAge
        });

        setCaptureData(data);
      } catch (err) {
        console.error('❌ Error receiving capture data:', err);
        setError(err instanceof Error ? err.message : 'An error occurred');
      }
    };

    // Handle API response
    const handleApiResponse = async () => {
      try {
        console.log('📥 Waiting for API response...');
        const response = await window.electron.waitForApiResponse();
        
        if (!response) {
          console.error('❌ No API response received');
          setError('No API response received');
          return;
        }

        console.log('📥 Received API response:', response);
        
        // Check for API error
        if (response.error) {
          console.error('❌ API returned error:', response.error);
          setError(response.error);
          return;
        }
        
        setApiResponse(response);
        
        if (response.options && Array.isArray(response.options)) {
          console.log('🔄 Processing API response options:', response.options);
          setOptions(response.options);
        } else {
          console.error('❌ Invalid options in API response');
          setError('Invalid options received from API');
        }

      } catch (err) {
        console.error('❌ Error receiving API response:', err);
        setError(err instanceof Error ? err.message : 'An error occurred');
      }
    };

    // Handle API error
    const handleApiError = async () => {
      try {
        console.log('⚠️ Waiting for API error...');
        const errorMessage = await window.electron.waitForApiError();
        
        if (errorMessage) {
          console.error('❌ API error received:', errorMessage);
          setError(`API Error: ${errorMessage}`);
        }
      } catch (err) {
        console.error('❌ Error handling API error:', err);
        setError('Failed to handle API error');
      }
    };

    // Start listening for events
    handleCaptureData();
    handleApiResponse();
    handleApiError();

    // Cleanup
    return () => {
      unsubscribeLoading();
    };
  }, []);
  
  const handleOptionSelect = useCallback(async (option: Option) => {
    try {
      console.log('🎯 Option selected in subwindow:', {
        id: option.id,
        title: option.title,
        description: option.description
      });
      
      // Send selected option to coordinator API
      if (window.electron) {
        // Create a plain object with only the necessary serializable properties
        const serializedOption = {
          id: String(option.id),
          title: String(option.title || ''),
          description: String(option.description || '')
        };
        
        console.log('📤 Sending option through IPC:', serializedOption);
        const result = await window.electron.sendSelectedOption(serializedOption);
        console.log('📤 IPC send result:', result);
      }
      
      // Open main window and close sub window
      if (window.electron) {
        console.log('🪟 Opening main window and closing subwindow');
        window.electron.openMainWindow();
        window.electron.closeSubWindow();
      }
      
      return true;
    } catch (err) {
      console.error('❌ Error in handleOptionSelect:', err);
      const errorMessage = err instanceof Error ? err.message : 'Failed to process selection';
      setError(errorMessage);
      return false;
    }
  }, []);
  
  const handleClose = useCallback(() => {
    console.log('🪟 Closing subwindow from useSubWindow');
    try {
      if (window.electron) {
        console.log('🪟 Electron API available, calling closeSubWindow');
        window.electron.closeSubWindow();
        console.log('🪟 closeSubWindow called successfully');
      } else {
        console.error('❌ Electron API not available');
      }
    } catch (error) {
      console.error('❌ Error closing subwindow:', error);
    }
  }, []);
  
  const openMainWindow = useCallback(() => {
    if (window.electron) {
      window.electron.openMainWindow();
      window.electron.closeSubWindow();
    }
  }, []);
  
  return {
    isLoading,
    error,
    options,
    captureData,
    apiResponse,
    selectedText: captureData?.text || '',
    handleOptionSelect,
    handleClose,
    openMainWindow,
  };
};

export default useSubWindow; 