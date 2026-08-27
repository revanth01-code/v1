import axios from 'axios';

const API_BASE_URL =
  import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000/api/v1';

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Interceptor to attach token
apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token');

    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`;
    }

    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Interceptor to format errors
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    let message = 'An unexpected error occurred';
    let feasibilityDetails = null;

    if (error.response) {
      // Handle 401 unauthorized globally
      if (error.response.status === 401) {
        localStorage.removeItem('token');

        if (!window.location.pathname.includes('/login')) {
          window.location.href = '/login';
        }
      }

      const data = error.response.data;

      if (data && typeof data === 'object') {
        // FastAPI validation detail lists or string messages
        if (typeof data.detail === 'string') {
          message = data.detail;
        } else if (Array.isArray(data.detail)) {
          message = data.detail
            .map((err: any) => err.msg || JSON.stringify(err))
            .join(', ');
        } else if (data.message) {
          message = data.message;
        }

        // Expose feasibility blockage info for Goals (422)
        if (data.feasibility) {
          feasibilityDetails = data.feasibility;
        }
      }
    } else if (error.request) {
      message = 'Cannot connect to server. Please check your network connection.';
    } else {
      message = error.message;
    }

    const customError = new Error(message) as any;

    customError.status = error.response?.status;
    customError.feasibility = feasibilityDetails;
    customError.originalError = error;

    return Promise.reject(customError);
  }
);