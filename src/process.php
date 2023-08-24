<?php
$servername = "mysql";
$username = "php";
$password = "php";

// Create connection
$conn = mysqli_connect($servername, $username, $password);
//
// Check connection
 if (!$conn) {
   die("Connection failed: " . mysqli_connect_error());
   }
   echo "SQL connected successfully! <br>";
   echo "Server Info: ". mysqli_get_server_info($conn);
?>
