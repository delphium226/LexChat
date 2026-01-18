import React, { useState, useEffect } from 'react';
import axios from 'axios';

const AdminPortal = () => {
    const [users, setUsers] = useState([]);
    const [loading, setLoading] = useState(true);
    const [newUser, setNewUser] = useState({ username: '', password: '', role: 'user', email: '' });
    const [editingUser, setEditingUser] = useState(null);
    const [message, setMessage] = useState('');

    const fetchUsers = async () => {
        try {
            const { data } = await axios.get('/api/users');
            setUsers(data);
        } catch (error) {
            console.error('Failed to fetch users', error);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchUsers();
    }, []);

    const handleCreateOrUpdateUser = async (e) => {
        e.preventDefault();
        try {
            if (editingUser) {
                await axios.put(`/api/users/${editingUser.id}`, newUser);
                setMessage('User updated successfully');
                setEditingUser(null);
            } else {
                await axios.post('/api/users', newUser);
                setMessage('User created successfully');
            }
            setNewUser({ username: '', password: '', role: 'user', email: '' });
            fetchUsers();
        } catch (error) {
            setMessage(error.response?.data?.message || (editingUser ? 'Error updating user' : 'Error creating user'));
        }
    };

    const startEditing = (user) => {
        setEditingUser(user);
        setNewUser({ username: user.username, password: '', role: user.role, email: user.email || '' });
        setMessage('');
    };

    const cancelEditing = () => {
        setEditingUser(null);
        setNewUser({ username: '', password: '', role: 'user', email: '' });
        setMessage('');
    };

    const handleDeleteUser = async (id) => {
        if (!window.confirm('Are you sure you want to delete this user?')) return;
        try {
            await axios.delete(`/api/users/${id}`);
            fetchUsers();
        } catch (error) {
            alert(error.response?.data?.message || 'Error deleting user');
        }
    };

    if (loading) return <div>Loading users...</div>;

    return (
        <div className="p-6">
            <h1 className="text-3xl font-bold mb-6 dark:text-white">Admin Portal</h1>

            {message && (
                <div className="bg-blue-100 border border-blue-400 text-blue-700 px-4 py-3 rounded mb-4">
                    {message}
                </div>
            )}

            <div className="bg-white dark:bg-zinc-800 p-6 rounded-lg shadow mb-8">
                <h2 className="text-xl font-bold mb-4 dark:text-white">{editingUser ? 'Edit User' : 'Add New User'}</h2>
                <form onSubmit={handleCreateOrUpdateUser} className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <input
                        type="text"
                        placeholder="Username"
                        value={newUser.username}
                        onChange={(e) => setNewUser({ ...newUser, username: e.target.value })}
                        className="p-2 border rounded dark:bg-zinc-700 dark:text-white"
                        required
                    />
                    <input
                        type="password"
                        placeholder={editingUser ? "Leave blank to keep current password" : "Password"}
                        value={newUser.password}
                        onChange={(e) => setNewUser({ ...newUser, password: e.target.value })}
                        className="p-2 border rounded dark:bg-zinc-700 dark:text-white"
                        required={!editingUser}
                    />
                    <input
                        type="email"
                        placeholder="Email"
                        value={newUser.email}
                        onChange={(e) => setNewUser({ ...newUser, email: e.target.value })}
                        className="p-2 border rounded dark:bg-zinc-700 dark:text-white"
                    />
                    <select
                        value={newUser.role}
                        onChange={(e) => setNewUser({ ...newUser, role: e.target.value })}
                        className="p-2 border rounded dark:bg-zinc-700 dark:text-white"
                    >
                        <option value="user">User</option>
                        <option value="admin">Admin</option>
                    </select>
                    <button
                        type="submit"
                        className="bg-green-500 hover:bg-green-600 text-white font-bold py-2 px-4 rounded md:col-span-2"
                    >
                        {editingUser ? 'Update User' : 'Create User'}
                    </button>
                    {editingUser && (
                        <button
                            type="button"
                            onClick={cancelEditing}
                            className="bg-gray-500 hover:bg-gray-600 text-white font-bold py-2 px-4 rounded md:col-span-2"
                        >
                            Cancel
                        </button>
                    )}
                </form>
            </div>

            <div className="bg-white dark:bg-zinc-800 p-6 rounded-lg shadow">
                <h2 className="text-xl font-bold mb-4 dark:text-white">Existing Users</h2>
                <div className="overflow-x-auto">
                    <table className="min-w-full leading-normal">
                        <thead>
                            <tr>
                                <th className="px-5 py-3 border-b-2 border-zinc-200 dark:border-zinc-700 text-left text-xs font-semibold text-zinc-600 dark:text-zinc-300 uppercase tracking-wider">
                                    Username
                                </th>
                                <th className="px-5 py-3 border-b-2 border-zinc-200 dark:border-zinc-700 text-left text-xs font-semibold text-zinc-600 dark:text-zinc-300 uppercase tracking-wider">
                                    Role
                                </th>
                                <th className="px-5 py-3 border-b-2 border-zinc-200 dark:border-zinc-700 text-left text-xs font-semibold text-zinc-600 dark:text-zinc-300 uppercase tracking-wider">
                                    Email
                                </th>
                                <th className="px-5 py-3 border-b-2 border-zinc-200 dark:border-zinc-700 text-left text-xs font-semibold text-zinc-600 dark:text-zinc-300 uppercase tracking-wider">
                                    Actions
                                </th>
                            </tr>
                        </thead>
                        <tbody>
                            {users.map((user) => (
                                <tr key={user.id}>
                                    <td className="px-5 py-5 border-b border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-sm dark:text-gray-200">
                                        {user.username}
                                    </td>
                                    <td className="px-5 py-5 border-b border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-sm dark:text-gray-200">
                                        {user.role}
                                    </td>
                                    <td className="px-5 py-5 border-b border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-sm dark:text-gray-200">
                                        {user.email}
                                    </td>
                                    <td className="px-5 py-5 border-b border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-sm dark:text-gray-200">
                                        <button
                                            onClick={() => startEditing(user)}
                                            className="text-blue-500 hover:text-blue-700 mr-3"
                                        >
                                            Edit
                                        </button>
                                        <button
                                            onClick={() => handleDeleteUser(user.id)}
                                            className="text-red-500 hover:text-red-700"
                                        >
                                            Delete
                                        </button>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    );
};

export default AdminPortal;
