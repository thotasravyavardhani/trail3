import React, { useState } from 'react';
import { useForm } from 'react-hook-form';
import { useAuth } from '../contexts/AuthContext';
import { Navigate } from 'react-router-dom';

interface LoginFormData {
  email: string;
  password: string;
  imap_server: string;
  smtp_server: string;
  imap_port: number;
  smtp_port: number;
}

const Login: React.FC = () => {
  const { login, isAuthenticated } = useAuth();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [provider, setProvider] = useState<'gmail' | 'outlook' | 'custom'>('gmail');

  const { register, handleSubmit, setValue, formState: { errors } } = useForm<LoginFormData>({
    defaultValues: {
      imap_port: 993,
      smtp_port: 587,
    }
  });

  if (isAuthenticated) {
    return <Navigate to="/inbox" replace />;
  }

  const handleProviderChange = (selectedProvider: 'gmail' | 'outlook' | 'custom') => {
    setProvider(selectedProvider);
    
    if (selectedProvider === 'gmail') {
      setValue('imap_server', 'imap.gmail.com');
      setValue('smtp_server', 'smtp.gmail.com');
      setValue('imap_port', 993);
      setValue('smtp_port', 587);
    } else if (selectedProvider === 'outlook') {
      setValue('imap_server', 'outlook.office365.com');
      setValue('smtp_server', 'smtp-mail.outlook.com');
      setValue('imap_port', 993);
      setValue('smtp_port', 587);
    } else {
      setValue('imap_server', '');
      setValue('smtp_server', '');
    }
  };

  const onSubmit = async (data: LoginFormData) => {
    setLoading(true);
    setError('');
    
    try {
      await login(data);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-100">
      <div className="max-w-md w-full space-y-8 p-8 bg-white rounded-xl shadow-lg">
        <div className="text-center">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">QuMail</h1>
          <p className="text-gray-600">Quantum-Secure Email Client</p>
          <div className="mt-4 flex justify-center space-x-2">
            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
              🔐 OTP Encryption
            </span>
            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
              🛡️ AES-256-GCM
            </span>
            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-purple-100 text-purple-800">
              ⚛️ PQC Ready
            </span>
          </div>
        </div>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
          {/* Email Provider Selection */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Email Provider
            </label>
            <div className="grid grid-cols-3 gap-2">
              {(['gmail', 'outlook', 'custom'] as const).map((p) => (
                <button
                  key={p}
                  type="button"
                  onClick={() => handleProviderChange(p)}
                  className={`px-3 py-2 text-sm font-medium rounded-md border ${
                    provider === p
                      ? 'bg-blue-600 text-white border-blue-600'
                      : 'bg-gray-50 text-gray-700 border-gray-300 hover:bg-gray-100'
                  }`}
                >
                  {p.charAt(0).toUpperCase() + p.slice(1)}
                </button>
              ))}
            </div>
          </div>

          {/* Email and Password */}
          <div className="space-y-4">
            <div>
              <label htmlFor="email" className="block text-sm font-medium text-gray-700">
                Email Address
              </label>
              <input
                {...register('email', { 
                  required: 'Email is required',
                  pattern: {
                    value: /^[^\s@]+@[^\s@]+\.[^\s@]+$/,
                    message: 'Invalid email address'
                  }
                })}
                type="email"
                className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500"
                placeholder="your-email@example.com"
              />
              {errors.email && (
                <p className="mt-1 text-sm text-red-600">{errors.email.message}</p>
              )}
            </div>

            <div>
              <label htmlFor="password" className="block text-sm font-medium text-gray-700">
                App Password
              </label>
              <input
                {...register('password', { required: 'Password is required' })}
                type="password"
                className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500"
                placeholder="App-specific password"
              />
              {errors.password && (
                <p className="mt-1 text-sm text-red-600">{errors.password.message}</p>
              )}
              <p className="mt-1 text-xs text-gray-500">
                Use app-specific passwords for Gmail/Outlook
              </p>
            </div>
          </div>

          {/* Server Configuration */}
          {provider === 'custom' && (
            <div className="space-y-4 p-4 bg-gray-50 rounded-md">
              <h3 className="text-sm font-medium text-gray-900">Server Configuration</h3>
              
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700">
                    IMAP Server
                  </label>
                  <input
                    {...register('imap_server', { required: 'IMAP server is required' })}
                    className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500"
                    placeholder="imap.example.com"
                  />
                  {errors.imap_server && (
                    <p className="mt-1 text-sm text-red-600">{errors.imap_server.message}</p>
                  )}
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-gray-700">
                    IMAP Port
                  </label>
                  <input
                    {...register('imap_port', { required: 'IMAP port is required' })}
                    type="number"
                    className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500"
                  />
                  {errors.imap_port && (
                    <p className="mt-1 text-sm text-red-600">{errors.imap_port.message}</p>
                  )}
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-gray-700">
                    SMTP Server
                  </label>
                  <input
                    {...register('smtp_server', { required: 'SMTP server is required' })}
                    className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500"
                    placeholder="smtp.example.com"
                  />
                  {errors.smtp_server && (
                    <p className="mt-1 text-sm text-red-600">{errors.smtp_server.message}</p>
                  )}
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-gray-700">
                    SMTP Port
                  </label>
                  <input
                    {...register('smtp_port', { required: 'SMTP port is required' })}
                    type="number"
                    className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500"
                  />
                  {errors.smtp_port && (
                    <p className="mt-1 text-sm text-red-600">{errors.smtp_port.message}</p>
                  )}
                </div>
              </div>
            </div>
          )}

          {error && (
            <div className="bg-red-50 border border-red-200 rounded-md p-3">
              <p className="text-sm text-red-600">{error}</p>
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? (
              <>
                <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                Connecting...
              </>
            ) : (
              'Connect to QuMail'
            )}
          </button>
        </form>

        <div className="text-center text-xs text-gray-500">
          <p>Secure authentication with quantum key distribution</p>
          <p className="mt-1">Your credentials are never stored or logged</p>
        </div>
      </div>
    </div>
  );
};

export default Login;